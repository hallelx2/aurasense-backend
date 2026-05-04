"""ProfileAgentState — extends BaseAgentState for the profile agent's graph."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.agents.base.state import BaseAgentState


class ProfileAgentState(BaseAgentState, total=False):
    """State carried through the profile agent's LangGraph.

    The profile agent is unusual in that its main "interface" isn't a
    user conversation — it's the synchronous ``get_user_context`` read
    API every other agent calls. The graph only runs when the agent
    receives an event from another agent (e.g. food agent records a
    visit; the graph normalizes + persists). State here is therefore
    minimal compared to the conversational agents.
    """

    # The intent that triggered this run (e.g. "food", "profile"). Drives
    # which Graphiti kinds get pulled and how the snapshot is shaped.
    intent: str

    # Output: serialized UserContextSnapshot.to_dict() — what the graph
    # ultimately produced. Stored in state so RedisSaver round-trips it.
    snapshot: Optional[Dict[str, Any]]
