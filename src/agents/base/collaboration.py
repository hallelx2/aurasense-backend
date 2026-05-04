"""
Cross-agent collaboration primitives.

Three channels (all required for "agents that talk to each other"):

1. **Sync service calls** — agents inject service facades
   (``profile_service``, ``social_service``, etc.) and call their read APIs
   directly. Agents NEVER import each other's graphs / nodes; that's what
   the service layer is for.

2. **State-level handoffs** — a node calls :func:`request_handoff` to mark
   its turn complete and ask the supervisor to route to a different
   specialist. The supervisor's post-specialist edge inspects
   ``state["handoff_to"]`` and re-routes.

3. **Async fan-out via Graphiti** — every agent's ``record_node`` writes
   typed episodes; every agent's ``context_node`` reads recent episodes.
   Travel doesn't need to know food exists — food's next-turn
   ``context_node`` will see ``TravelContext`` because travel wrote it.

This module only owns channel 2 (state handoffs). Channels 1 and 3 are in
``services/*_service.py`` and ``services/graphiti/`` respectively.
"""

from __future__ import annotations

from typing import Dict, List, TypeVar

from .state import BaseAgentState

S = TypeVar("S", bound=BaseAgentState)


# Maximum number of agent-to-agent handoffs the supervisor will execute
# in a single user turn. Once exceeded, the supervisor falls through to a
# clarifying TTS response and the trail resets on the next user message.
MAX_HANDOFFS_PER_TURN = 3


def request_handoff(state: S, *, target: str, reason: str, source: str) -> S:
    """Mark this turn complete and ask the supervisor to route to ``target``.

    Mutates ``state`` in place AND returns it so node functions can do::

        return request_handoff(state, target="food", reason="...", source=self.name)
    """
    state["status"] = "needs_handoff"
    state["handoff_to"] = target
    trail: List[Dict[str, str]] = state.setdefault("handoff_trail", [])
    trail.append({"from": source, "to": target, "reason": reason})
    return state


def handoff_trail(state: BaseAgentState) -> List[Dict[str, str]]:
    """Read-only accessor for the handoff trail (always returns a list)."""
    return list(state.get("handoff_trail") or [])
