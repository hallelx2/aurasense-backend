"""
Supervisor-driven WebSocket route — ``/ws/agent``.

Single endpoint for all agentic interaction. Replaces the per-agent
WebSocket scheme (``/ws/onboarding`` is still alive for back-compat;
new clients should use ``/ws/agent``).

Flow per turn:

1. WS handler authenticates the bearer token and resolves the User.
2. For ``user_audio`` frames, it transcribes upstream (so the
   supervisor's state never carries raw bytes).
3. State for this turn is built from the user input + identity, then
   passed into the supervisor graph keyed by
   ``thread_id="supervisor:{user.uid}"`` so multi-turn state survives
   restarts.
4. The supervisor classifies intent, gates onboarding, routes to the
   right specialist, and ultimately produces a ``system_response``.
5. Handler sends the response back as an ``agent_message`` frame.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)

from src.agents.onboarding_agent.tools import transcribe_audio
from src.agents.supervisor import get_supervisor_graph
from src.agents.supervisor.state import SupervisorState
from src.app.api.routes.auth import security_manager
from src.app.core.config import settings
from src.app.core.database import run_in_thread
from src.app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------- auth


async def get_current_user_from_token(
    websocket: WebSocket,
    token: Optional[str] = None,
) -> User:
    if token is None:
        token = websocket.query_params.get("token")
    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Missing token"
        )

    try:
        token_data = await security_manager.verify_token(token)
        if not token_data:
            raise Exception("Invalid or expired token")
        user_id = token_data.get("sub")
        if not user_id:
            raise Exception("Invalid token payload")
        user = await run_in_thread(User.nodes.filter(uid=user_id).first)
        if not user:
            raise Exception("User not found")
        return user
    except Exception as e:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason=str(e)
        )


# ------------------------------------------------------- audio download


async def _download_audio(audio_url: str) -> bytes:
    """Bounded async download — same shape as the onboarding WS handler."""
    max_bytes = settings.MAX_AUDIO_FILE_SIZE_MB * 1024 * 1024
    timeout = aiohttp.ClientTimeout(total=settings.AUDIO_PROCESSING_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(audio_url) as response:
            response.raise_for_status()
            buffer = bytearray()
            async for chunk in response.content.iter_chunked(64 * 1024):
                buffer.extend(chunk)
                if len(buffer) > max_bytes:
                    raise ValueError(
                        f"Audio exceeds {settings.MAX_AUDIO_FILE_SIZE_MB} MB limit"
                    )
            return bytes(buffer)


# --------------------------------------------------------- send helpers


async def _send_agent_message(websocket: WebSocket, text: str) -> None:
    await websocket.send_json(
        {
            "type": "agent_message",
            "payload": {
                "id": str(uuid.uuid4()),
                "sender": "agent",
                "text": text,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
    )


async def _send_error(websocket: WebSocket, message: str) -> None:
    await websocket.send_json(
        {"type": "error", "payload": {"message": message}}
    )


async def _send_intent(websocket: WebSocket, intent: Optional[str]) -> None:
    """Echo the supervisor's classified intent — useful for the frontend
    to render which specialist is responding."""
    if not intent:
        return
    await websocket.send_json(
        {"type": "agent_intent", "payload": {"intent": intent}}
    )


# --------------------------------------------------------- core handler


def _supervisor_thread_id(user: User) -> str:
    """Canonical checkpointer thread id for this user's supervisor session."""
    return f"supervisor:{user.uid}"


async def _process_turn(
    *, websocket: WebSocket, user: User, user_text: str
) -> None:
    """Run one turn through the supervisor graph and emit the response."""
    graph = get_supervisor_graph()
    thread_id = _supervisor_thread_id(user)
    config = {"configurable": {"thread_id": thread_id}}

    initial: Dict[str, Any] = {
        "user_id": user.uid,
        "group_id": user.uid,
        "thread_id": thread_id,
        "agent_name": "supervisor",
        "user_input": user_text,
        "transcribed_text": user_text,
        "status": "pending_info",
        "messages": [],
    }

    try:
        final_state: Dict[str, Any] = await graph.ainvoke(initial, config=config)
    except Exception:
        logger.exception("supervisor.ainvoke failed for user=%s", user.uid)
        await _send_error(websocket, "Internal error processing your message.")
        return

    await _send_intent(websocket, final_state.get("intent"))
    response_text = final_state.get(
        "system_response", "I'm processing your message..."
    )
    await _send_agent_message(websocket, response_text)


# ---------------------------------------------------------------- route


@router.websocket("/ws/agent")
async def agent_ws(websocket: WebSocket) -> None:
    """Single agentic WebSocket endpoint. Routes intent → specialist."""
    await websocket.accept()
    try:
        user = await get_current_user_from_token(websocket)
    except WebSocketException as e:
        logger.warning("WS /ws/agent auth failed: %s", e.reason)
        await _send_error(websocket, f"Authentication failed: {e.reason}")
        await websocket.close()
        return

    logger.info(
        "agent WS connected",
        extra={"user_id": user.uid, "thread_id": _supervisor_thread_id(user)},
    )

    await _send_agent_message(
        websocket,
        f"Hi {user.first_name}! What would you like to do?",
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error(websocket, "Invalid JSON frame")
                continue

            msg_type = data.get("type")
            payload = data.get("payload", {})

            try:
                if msg_type == "user_audio":
                    audio_url = payload.get("audioUrl")
                    if not audio_url:
                        raise ValueError("user_audio frame missing audioUrl")
                    audio_bytes = await _download_audio(audio_url)
                    transcript_obj = await transcribe_audio(audio_bytes)
                    transcript = (
                        transcript_obj
                        if isinstance(transcript_obj, str)
                        else transcript_obj.get("text", "")
                    )
                    await _process_turn(
                        websocket=websocket, user=user, user_text=transcript
                    )

                elif msg_type == "user_message":
                    text = (payload.get("text") or "").strip()
                    if not text:
                        continue
                    await _process_turn(
                        websocket=websocket, user=user, user_text=text
                    )

                else:
                    logger.debug("unknown WS frame type: %s", msg_type)

            except Exception as e:
                logger.exception("error handling /ws/agent turn")
                await _send_error(websocket, f"Error: {e}")

    except WebSocketDisconnect:
        logger.info("agent WS disconnected", extra={"user_id": user.uid})
    except Exception as e:
        logger.exception("unexpected /ws/agent error")
        try:
            await _send_error(websocket, str(e))
            await websocket.close()
        except Exception:
            pass
