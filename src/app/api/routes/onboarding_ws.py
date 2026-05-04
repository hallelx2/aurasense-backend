"""WebSocket route for the voice-first onboarding agent.

Per Phase 1 the agent's multi-turn state lives in Redis (via the shared
`AsyncRedisSaver`), keyed by ``thread_id = "onboarding:{user.uid}"``. The
old per-process ``onboarding_sessions`` dict is gone — state survives
container restarts and works across multiple workers.

Audio transcription is performed **here** in the WS route, not inside the
graph, so the checkpointed state never carries raw bytes (unserializable
through Redis).
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

from src.agents.onboarding_agent.agent import onboarding_agent
from src.agents.onboarding_agent.state import OnboardingAgentState
from src.agents.onboarding_agent.tools import transcribe_audio
from src.app.api.routes.auth import security_manager
from src.app.core.config import settings
from src.app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


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

        user = User.nodes.filter(uid=user_id).first()
        if not user:
            raise Exception("User not found")

        return user
    except Exception as e:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason=str(e)
        )


# --------------------------------------------------------------------------
# Audio download (async, bounded)
# --------------------------------------------------------------------------


async def download_audio_from_url(audio_url: str) -> bytes:
    """Download audio non-blockingly with a size guard."""
    max_bytes = settings.MAX_AUDIO_FILE_SIZE_MB * 1024 * 1024
    timeout = aiohttp.ClientTimeout(total=settings.AUDIO_PROCESSING_TIMEOUT)
    try:
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
    except Exception as e:
        raise Exception(f"Failed to download audio: {e}") from e


# --------------------------------------------------------------------------
# Frontend message envelope helpers
# --------------------------------------------------------------------------

_STEP_TO_PROGRESS_KEY = {
    "dietary_restrictions": "dietaryPreferences",
    "cuisine_preferences": "dietaryPreferences",
    "allergies": "restrictions",
    "health_conditions": "allergies",
    "voice_sample": "voiceSample",
    "cultural_background": "communityInterests",
    "general": "dietaryPreferences",
}


def map_onboarding_step_to_progress(step: str, is_complete: bool) -> Dict[str, Any]:
    return {
        "key": _STEP_TO_PROGRESS_KEY.get(step, "dietaryPreferences"),
        "value": is_complete,
    }


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


async def _send_progress(
    websocket: WebSocket, step: str, is_complete: bool
) -> None:
    await websocket.send_json(
        {
            "type": "onboarding_progress",
            "payload": map_onboarding_step_to_progress(step, is_complete),
        }
    )


async def _send_completion_progress(websocket: WebSocket) -> None:
    """Mark every checklist key complete (sent when status flips to onboarded)."""
    for key in (
        "dietaryPreferences",
        "restrictions",
        "allergies",
        "voiceSample",
        "communityInterests",
    ):
        await websocket.send_json(
            {
                "type": "onboarding_progress",
                "payload": {"key": key, "value": True},
            }
        )


# --------------------------------------------------------------------------
# Agent invocation (thread_id-aware: resumes from Redis when present)
# --------------------------------------------------------------------------


def _build_existing_user_snapshot(user: User) -> Dict[str, Any]:
    """Snapshot of fields already known about the user from sign-up."""
    return {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": getattr(user, "username", None),
        "phone": getattr(user, "phone", None),
        "age": getattr(user, "age", None),
        "dietary_restrictions": getattr(user, "dietary_restrictions", []),
        "cuisine_preferences": getattr(user, "cuisine_preferences", []),
        "price_range": getattr(user, "price_range", None),
        "is_tourist": getattr(user, "is_tourist", False),
    }


async def _invoke_agent(
    *, user: User, user_text: str, thread_id: str
) -> OnboardingAgentState:
    """Invoke the onboarding agent, resuming from the Redis checkpoint if any.

    First turn for a thread: pass full initial state (existing user snapshot
    pre-loaded). Subsequent turns: pass only the new ``user_input`` so
    LangGraph merges it into the checkpointed state instead of clobbering
    the accumulated extracted information.
    """
    graph = onboarding_agent.compile()
    config = {"configurable": {"thread_id": thread_id}}

    snapshot = await graph.aget_state(config)
    has_prior_state = bool(snapshot and snapshot.values)

    if has_prior_state:
        return await graph.ainvoke({"user_input": user_text}, config=config)

    initial: OnboardingAgentState = {
        "user_input": user_text,
        "user_id": user.uid,
        "group_id": user.uid,
        "thread_id": thread_id,
        "agent_name": onboarding_agent.name,
        "extracted_information": _build_existing_user_snapshot(user),
        "onboarding_status": "pending_info",
        "messages": [],
    }
    return await graph.ainvoke(initial, config=config)


async def _process_user_turn(
    *,
    websocket: WebSocket,
    user: User,
    thread_id: str,
    step: str,
    user_text: str,
) -> None:
    """Run one user turn and emit the agent's response + progress frames."""
    final_state = await _invoke_agent(
        user=user, user_text=user_text, thread_id=thread_id
    )

    response_text = final_state.get(
        "system_response", "I'm processing your information..."
    )
    onboarding_status = final_state.get("onboarding_status", "pending_info")

    await _send_agent_message(websocket, response_text)
    await _send_progress(
        websocket, step, is_complete=onboarding_status in ("ready", "onboarded")
    )

    if onboarding_status == "onboarded":
        await _send_agent_message(
            websocket,
            f"Fantastic, {user.first_name}! Your personalization is complete. "
            "Aurasense is now tailored to your preferences and ready to provide "
            "you with amazing recommendations!",
        )
        await _send_completion_progress(websocket)


# --------------------------------------------------------------------------
# WebSocket endpoint
# --------------------------------------------------------------------------


@router.websocket("/ws/onboarding")
async def onboarding_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        user = await get_current_user_from_token(websocket)
    except WebSocketException as e:
        logger.warning("WS auth failed: %s", e.reason)
        await websocket.send_json(
            {
                "type": "error",
                "payload": {"message": f"Authentication failed: {e.reason}"},
            }
        )
        await websocket.close()
        return

    thread_id = onboarding_agent.thread_id_for(user.uid)
    logger.info("WS onboarding connected: user=%s thread=%s", user.email, thread_id)

    # Initial greeting: identify whether onboarding has already collected
    # everything we need from sign-up. (Once Phase 2 lands, this should
    # consult Graphiti so we don't re-ask things from a prior session.)
    missing_fields = [
        f
        for f in (
            "age",
            "dietary_restrictions",
            "cuisine_preferences",
            "price_range",
            "is_tourist",
        )
        if not getattr(user, f, None)
    ]
    if missing_fields:
        await _send_agent_message(
            websocket,
            "I need a few more details to personalize your experience. "
            "Let's start with your age — how old are you?",
        )
    else:
        await _send_agent_message(
            websocket,
            "Your profile looks complete! Is there anything specific you'd "
            "like to update or add?",
        )

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")
            payload = data.get("payload", {})

            try:
                if msg_type == "user_audio":
                    audio_url = payload.get("audioUrl")
                    if not audio_url:
                        raise ValueError("user_audio frame missing audioUrl")
                    audio_bytes = await download_audio_from_url(audio_url)
                    transcript_obj = await transcribe_audio(audio_bytes)
                    transcript = (
                        transcript_obj
                        if isinstance(transcript_obj, str)
                        else transcript_obj.get("text", "")
                    )
                    await _process_user_turn(
                        websocket=websocket,
                        user=user,
                        thread_id=thread_id,
                        step=payload.get("step", "general"),
                        user_text=transcript,
                    )

                elif msg_type == "user_message":
                    text = payload.get("text", "").strip()
                    if not text:
                        continue
                    await _process_user_turn(
                        websocket=websocket,
                        user=user,
                        thread_id=thread_id,
                        step=payload.get("step", "general"),
                        user_text=text,
                    )

                else:
                    logger.debug("Unknown WS message type: %s", msg_type)

            except Exception as e:
                logger.exception("error handling WS turn")
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {"message": f"Error: {e}"},
                    }
                )

    except WebSocketDisconnect:
        logger.info("WS onboarding disconnected: user=%s", user.email)
    except Exception as e:
        logger.exception("unexpected WS error")
        try:
            await websocket.send_json(
                {"type": "error", "payload": {"message": str(e)}}
            )
            await websocket.close()
        except Exception:
            pass
