"""
Supervisor LangGraph nodes.

The supervisor is intentionally thin:

1. ``ingest`` — copy ``user_input`` into ``transcribed_text`` if STT
   already happened upstream (the WS handler does it for audio frames).
2. ``onboarding_gate`` — if ``User.is_onboarded`` is False, force
   intent='onboarding' and skip classification.
3. ``classify`` — single LLM call, structured output → intent.
4. Conditional edge to the matching specialist sub-graph.

Specialists return state and the supervisor's ``post_specialist`` edge
inspects ``state.handoff_to`` for cross-agent re-routing (Channel #2 of
collaboration). ``MAX_HANDOFFS_PER_TURN`` caps loops.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.agents.base.collaboration import MAX_HANDOFFS_PER_TURN
from src.app.core.database import run_in_thread
from src.app.models.user import User
from src.app.services.llm_gateway import gateway

from .intents import MIN_CONFIDENCE, IntentChoice, build_intent_prompt
from .state import SupervisorIntent, SupervisorState

logger = logging.getLogger(__name__)


# ============================================================ INGEST


async def ingest_node(state: SupervisorState) -> SupervisorState:
    """Mirror user_input → transcribed_text if upstream didn't already."""
    if not state.get("transcribed_text"):
        ui = state.get("user_input")
        if isinstance(ui, str) and ui.strip():
            state["transcribed_text"] = ui
    return state


# ============================================================ GATE


async def onboarding_gate_node(state: SupervisorState) -> SupervisorState:
    """Force-route to the onboarding agent if the user isn't onboarded yet.

    This runs BEFORE classification. The food / travel / social agents
    assume the user has at least basic preferences set; if they don't,
    we always finish onboarding first.
    """
    user_id = state.get("user_id")
    if not user_id:
        # No user → can't gate; let classify decide.
        state["onboarding_gate_forced"] = False
        return state

    try:
        user = await run_in_thread(User.nodes.filter(uid=user_id).first)
    except Exception:
        logger.exception("supervisor.onboarding_gate user lookup failed")
        user = None

    if user is not None and not bool(getattr(user, "is_onboarded", False)):
        state["intent"] = "onboarding"
        state["onboarding_gate_forced"] = True
    else:
        state["onboarding_gate_forced"] = False
    return state


# ============================================================ CLASSIFY


async def classify_node(state: SupervisorState) -> SupervisorState:
    """LLM-classify the user's utterance into an intent.

    Skipped if the onboarding gate already pinned the intent.
    """
    if state.get("onboarding_gate_forced") and state.get("intent"):
        return state

    user_text = (state.get("transcribed_text") or state.get("user_input") or "").strip()
    if not user_text:
        state["intent"] = "off_topic"
        return state

    try:
        llm = gateway.get_llm("supervisor")
        classifier = llm.with_structured_output(IntentChoice)
        result = await classifier.ainvoke(build_intent_prompt(user_text))
    except Exception:
        logger.exception("supervisor.classify failed; defaulting to off_topic")
        state["intent"] = "off_topic"
        return state

    if result.confidence < MIN_CONFIDENCE:
        logger.info(
            "supervisor.classify low confidence (%.2f); intent=%s reason=%s",
            result.confidence,
            result.intent,
            result.reasoning,
        )
        state["intent"] = "off_topic"
    else:
        state["intent"] = result.intent

    logger.info(
        "supervisor.classify result",
        extra={
            "intent": state.get("intent"),
            "confidence": result.confidence,
            "reasoning": result.reasoning[:200] if result.reasoning else "",
        },
    )
    return state


# ============================================================ ROUTING


def route_to_specialist(state: SupervisorState) -> str:
    """Conditional edge target after ``classify_node``."""
    intent = state.get("intent") or "off_topic"
    if intent in ("onboarding", "food", "profile"):
        return intent
    return "off_topic_response"


def route_after_specialist(state: SupervisorState) -> str:
    """After a specialist runs: handoff to another agent, or finish.

    Implements channel #2 of cross-agent collaboration. Capped at
    ``MAX_HANDOFFS_PER_TURN`` hops per turn to prevent loops.
    """
    if state.get("status") == "needs_handoff" and state.get("handoff_to"):
        trail = state.get("handoff_trail") or []
        if len(trail) <= MAX_HANDOFFS_PER_TURN:
            target = state["handoff_to"]
            if target in ("onboarding", "food", "profile"):
                # Clear the handoff flag for the next iteration to avoid
                # the specialist re-emitting the same handoff.
                state["status"] = "ready"
                state["handoff_to"] = None
                return target
        # Hop limit hit → fall through to finish with a clarification.
        state["system_response"] = (
            state.get("system_response")
            or "Let me clarify — what would you like to do next?"
        )
    return "finish"


# ============================================================ OFF-TOPIC


_OFF_TOPIC_FALLBACK = (
    "I'm a food & lifestyle assistant — I can help with meal recommendations, "
    "ordering, travel, and finding people to connect with. What would you like "
    "to do?"
)


async def off_topic_node(state: SupervisorState) -> SupervisorState:
    """Polite redirect when classification didn't match a specialist."""
    state["system_response"] = state.get("system_response") or _OFF_TOPIC_FALLBACK
    state["status"] = "ready"
    return state


# ============================================================ FINISH


async def finish_node(state: SupervisorState) -> SupervisorState:
    """Terminal node — ensures status is set so callers can short-circuit."""
    if state.get("status") not in ("ready", "complete"):
        state["status"] = "ready"
    return state
