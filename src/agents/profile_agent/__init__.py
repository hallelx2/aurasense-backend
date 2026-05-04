"""Profile / Context Manager agent package.

Public surface:

* :class:`ProfileAgent` — the LangGraph-backed agent class.
* :data:`profile_agent` — module-level singleton.
* :class:`UserContextSnapshot` — the structured payload other agents read.
* :class:`ProfileAgentState` — TypedDict for the agent's graph state.
"""

from .agent import ProfileAgent, profile_agent
from .snapshot import UserContextSnapshot
from .state import ProfileAgentState

__all__ = [
    "ProfileAgent",
    "ProfileAgentState",
    "UserContextSnapshot",
    "profile_agent",
]
