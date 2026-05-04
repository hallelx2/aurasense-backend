"""
BaseAgentState — the shared TypedDict every specialist agent state extends.

Keep field types to plain serializable values (str / dict / list / int).
The state is persisted by LangGraph's RedisSaver between turns, so anything
that doesn't round-trip cleanly through JSON-ish serialization (raw bytes,
Pydantic v2 models, custom classes) belongs *outside* the state — usually
in Graphiti episodes or in Redis as side-data keyed by ``thread_id``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage


# Status the orchestrator inspects after a specialist returns. ``ready`` =
# specialist finished its turn and the supervisor should respond to the
# user. ``needs_handoff`` = re-route per ``handoff_to``. ``complete`` =
# specialist is fully done and shouldn't be re-entered for this thread
# (e.g. onboarding). ``failed`` = surface the error in ``error``.
AgentStatus = Literal[
    "pending_info",
    "ready",
    "needs_handoff",
    "complete",
    "failed",
]


class BaseAgentState(TypedDict, total=False):
    """Common state shape every agent reads and writes.

    All specialist agent states should extend this with their own fields::

        class FoodAgentState(BaseAgentState, total=False):
            cart: list[dict]
            health_filters: dict
    """

    # --- Identity ----------------------------------------------------------
    user_id: str            # = User.uid; canonical inside the backend
    group_id: str           # = user_id; Graphiti scoping namespace
    thread_id: str          # LangGraph checkpoint key; supervisor sets it
    agent_name: str         # the specialist that last wrote this state

    # --- Turn input -------------------------------------------------------
    user_input: str         # raw text or transcript (NOT bytes — see module docstring)
    transcribed_text: Optional[str]
    messages: List[BaseMessage]   # capped, summarized conversation history

    # --- Context (read from Graphiti by `context_node`) -------------------
    retrieved_context: Dict[str, Any]

    # --- Outputs ----------------------------------------------------------
    extracted_facts: Dict[str, Any]   # what `record_node` writes to Graphiti
    system_response: Optional[str]
    response_audio_path: Optional[str]

    # --- Control flow ----------------------------------------------------
    status: AgentStatus
    handoff_to: Optional[str]               # name of the next agent
    handoff_trail: List[Dict[str, str]]     # [{from, to, reason}, ...]
    error: Optional[str]
