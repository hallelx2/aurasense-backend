"""
BaseAgent — the abstraction every specialist agent extends.

A specialist's job is to implement :meth:`build_graph` (registering its
nodes and edges on a freshly-created :class:`StateGraph`). The base class
handles:

* LLM access via the gateway (``self.llm`` and ``self.with_structured_output``)
* Cross-agent handoff (``self.hand_off_to``)
* Default ``context_node`` (read Graphiti) and ``record_node`` (write Graphiti)
* Compilation with the shared :class:`AsyncRedisSaver` checkpointer
* Async invocation with the right ``thread_id`` config

Specialists never import each other or instantiate ``langchain_groq`` /
``langchain_openai`` directly. Every model call goes through the gateway;
every cross-agent read goes through a ``*_service.py`` facade.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, Type, TypeVar

from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph

from src.app.services.llm_gateway import gateway

from .checkpointer import get_async_redis_saver
from .collaboration import request_handoff
from .state import BaseAgentState

logger = logging.getLogger(__name__)

S = TypeVar("S", bound=BaseAgentState)


class BaseAgent(ABC, Generic[S]):
    """Abstract base for every specialist agent.

    Subclass contract::

        class FoodAgent(BaseAgent[FoodAgentState]):
            name = "food"
            state_cls = FoodAgentState
            relevant_entity_types = ["Allergy", "FoodPreference", ...]
            llm_role = "food"      # optional; falls back to "agent"

            def build_graph(self, workflow: StateGraph) -> None:
                workflow.add_node("transcribe", self.transcribe_node)
                ...
                workflow.set_entry_point("transcribe")
    """

    #: Stable identifier used in handoffs, logs, and Graphiti episode metadata.
    name: str = "base"

    #: TypedDict subclass for this agent's state. Pass to ``StateGraph(state_cls)``.
    state_cls: Type[S] = BaseAgentState  # type: ignore[assignment]

    #: Entity types relevant to this agent's intent. The default
    #: ``context_node`` filters Graphiti search by these.
    relevant_entity_types: list[str] = []

    #: LLM gateway role. Override per agent (``"food"``, ``"profile"`` …)
    #: or leave as ``"agent"`` to use the default profile.
    llm_role: str = "agent"

    def __init__(self) -> None:
        self._compiled = None  # cached compiled graph

    # -- LLM access (always via the gateway) -------------------------------

    @property
    def llm(self) -> BaseChatModel:
        """The chat model configured for this agent's role."""
        return gateway.get_llm(self.llm_role)

    def with_structured_output(self, schema: Any) -> Any:
        """Shortcut for ``self.llm.with_structured_output(schema)``."""
        return self.llm.with_structured_output(schema)

    # -- Subclass contract -------------------------------------------------

    @abstractmethod
    def build_graph(self, workflow: StateGraph) -> None:
        """Register nodes and edges on ``workflow``. Required."""

    # -- Default reusable nodes -------------------------------------------

    async def context_node(self, state: S) -> S:
        """Default: pull relevant Graphiti context for this agent's intent.

        Overridden when the specialist needs different filtering. The real
        Graphiti retriever lands in Phase 2; this is a no-op shim for now
        so subclasses can wire ``context_node`` into their graphs and have
        it Just Work later without re-plumbing.
        """
        try:
            from src.app.services.graphiti.retriever import get_relevant_context
        except ImportError:
            # Phase-2 module not yet present — skip.
            state.setdefault("retrieved_context", {})
            return state

        state["retrieved_context"] = await get_relevant_context(
            user_id=state.get("user_id", ""),
            query=state.get("transcribed_text") or state.get("user_input", "") or "",
            kinds=self.relevant_entity_types,
        )
        return state

    async def record_node(self, state: S) -> S:
        """Default: write any extracted_facts as a Graphiti episode.

        Same Phase-2 shim as ``context_node``: no-op until the contract
        module exists, fully wired afterwards.
        """
        facts = state.get("extracted_facts") or {}
        if not facts:
            return state
        try:
            from src.app.services.graphiti.contract import record_extracted_facts
        except ImportError:
            return state

        await record_extracted_facts(
            user_id=state.get("user_id", ""),
            facts=facts,
            agent_name=self.name,
        )
        return state

    # -- Cross-agent collaboration -----------------------------------------

    def hand_off_to(self, state: S, target: str, *, reason: str = "") -> S:
        """Mark this turn complete; supervisor will route to ``target`` next."""
        return request_handoff(state, target=target, reason=reason, source=self.name)

    # -- Compile + invoke --------------------------------------------------

    def compile(self):
        """Lazily compile the StateGraph with the shared async checkpointer."""
        if self._compiled is None:
            workflow = StateGraph(self.state_cls)
            self.build_graph(workflow)
            self._compiled = workflow.compile(
                checkpointer=get_async_redis_saver(),
            )
            logger.info("agent %r: graph compiled with RedisSaver", self.name)
        return self._compiled

    async def ainvoke(self, state: S, *, thread_id: str) -> S:
        """Run the graph with the given ``thread_id`` for checkpoint scoping."""
        graph = self.compile()
        return await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": thread_id}},
        )

    # -- Identity helpers --------------------------------------------------

    def thread_id_for(self, user_id: str, suffix: Optional[str] = None) -> str:
        """Build the canonical thread id for ``(self, user)`` checkpoints.

        Default policy (locked in the plan): ``"{agent_name}:{user_id}"`` —
        one persistent thread per (agent, user). ``suffix`` exists so an
        agent can override for ephemeral / multi-cart sessions if needed.
        """
        base = f"{self.name}:{user_id}"
        return f"{base}:{suffix}" if suffix else base
