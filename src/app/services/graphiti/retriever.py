"""
Graphiti read contract — agents call into this to fetch user context
*before* responding, so personalization compounds across sessions.

The headline function is :func:`get_relevant_context`, used from every
agent's ``context_node``. It returns a :class:`ContextBundle` that
already knows how to serialize itself into:

* a JSON-ish dict (for storing into the LangGraph state, which
  RedisSaver round-trips), and
* a text snippet (for prompt injection).

Why a structured bundle and not just a string? We want individual nodes
to be able to consume specific kinds (``bundle.allergies``,
``bundle.cuisines``) without re-parsing free text, AND we want the
system prompt builder to drop the whole thing in with a uniform format.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

from graphiti_core.edges import EntityEdge

from .client import get_graphiti
from .entity_types import RELEVANT_BY_INTENT

logger = logging.getLogger(__name__)


# Default number of facts pulled per intent. Higher = richer context but
# more prompt tokens; 8 is a reasonable middle for voice-agent UX where
# response time matters.
DEFAULT_NUM_RESULTS = 8


@dataclass
class ContextBundle:
    """Structured user context retrieved from Graphiti for a given intent."""

    user_id: str
    intent: str
    facts: list[str] = field(default_factory=list)
    # facts is the raw "edge.fact" strings; the categorized buckets below
    # are best-effort parses based on edge name / attribute.
    by_kind: dict[str, list[str]] = field(default_factory=dict)
    raw_count: int = 0

    # ---------- Convenience accessors used by domain code ----------------

    def kind(self, *names: str) -> list[str]:
        """Return all facts whose categorized kind is in ``names``."""
        out: list[str] = []
        for n in names:
            out.extend(self.by_kind.get(n, ()))
        return out

    @property
    def allergies(self) -> list[str]:
        return self.kind("Allergy")

    @property
    def dietary_restrictions(self) -> list[str]:
        return self.kind("DietaryRestriction")

    @property
    def health_conditions(self) -> list[str]:
        return self.kind("HealthCondition")

    @property
    def cuisines(self) -> list[str]:
        return self.kind("FoodPreference")

    @property
    def cultural(self) -> list[str]:
        return self.kind("CulturalContext")

    @property
    def restaurant_visits(self) -> list[str]:
        return self.kind("RestaurantVisit")

    # -------------------- Serialization for state + prompts -------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "intent": self.intent,
            "facts": list(self.facts),
            "by_kind": {k: list(v) for k, v in self.by_kind.items()},
            "raw_count": self.raw_count,
        }

    def to_prompt(self) -> str:
        """Render as a clean text block to inject into an LLM prompt.

        Empty bundles render as a single hint line so the prompt is
        consistent ("we don't know much about this user yet").
        """
        if not self.facts:
            return "(No prior context found about the user yet.)"

        lines: list[str] = []
        for kind, items in self.by_kind.items():
            if not items:
                continue
            label = _PRETTY_LABEL.get(kind, kind)
            lines.append(f"- {label}: {', '.join(items)}")

        # Any facts not categorized fall through under "Other".
        categorized = {f for items in self.by_kind.values() for f in items}
        leftovers = [f for f in self.facts if f not in categorized]
        if leftovers:
            lines.append("- Other: " + "; ".join(leftovers[:5]))

        return "\n".join(lines) if lines else "(No prior context found about the user yet.)"

    # ------------------------------------------------- Construction

    @classmethod
    def empty(cls, user_id: str, intent: str) -> "ContextBundle":
        return cls(user_id=user_id, intent=intent)

    @classmethod
    def from_edges(
        cls,
        user_id: str,
        intent: str,
        edges: Iterable[EntityEdge],
    ) -> "ContextBundle":
        edges_list = list(edges)
        bundle = cls(user_id=user_id, intent=intent, raw_count=len(edges_list))
        for edge in edges_list:
            fact_text = (edge.fact or "").strip()
            if not fact_text:
                continue
            bundle.facts.append(fact_text)
            kind = _classify_edge(edge)
            bundle.by_kind.setdefault(kind, []).append(fact_text)
        return bundle


# ----------------------------------------------------------- Public API


async def get_relevant_context(
    *,
    user_id: str,
    query: str,
    kinds: Optional[Iterable[str]] = None,
    intent: str = "default",
    num_results: int = DEFAULT_NUM_RESULTS,
) -> ContextBundle:
    """Search Graphiti for context relevant to ``query`` for this user.

    Args:
        user_id: scoped via Graphiti ``group_ids=[user_id]``. CRITICAL
            for multi-user isolation — never omit.
        query: a free-text query used for vector + text retrieval. The
            agent should pass the user's current utterance + a hint
            phrase ("dietary preferences allergies cuisine").
        kinds: optional whitelist of entity-type names to keep (the
            search itself is not type-filtered today; this is a
            post-filter applied to ``ContextBundle.by_kind``). Defaults
            to ``RELEVANT_BY_INTENT[intent]`` if available.
        intent: an intent label used for default kind selection AND
            as a tag on the bundle.
        num_results: top-K from Graphiti search. Default 8.

    Returns:
        ContextBundle. On Graphiti error the bundle is empty (we never
        let memory failure break the user-facing flow).
    """
    if not user_id:
        return ContextBundle.empty(user_id="", intent=intent)
    if not query:
        # Empty query still returns recent facts via Graphiti's default
        # search behavior, but degenerates to (basically) nothing useful.
        # Substitute a neutral query that pulls top-N for this user.
        query = "user profile preferences"

    try:
        g = get_graphiti()
        edges = await g.search(
            query=query,
            group_ids=[user_id],
            num_results=num_results,
        )
    except Exception:
        logger.exception(
            "graphiti.search failed for user_id=%s intent=%s", user_id, intent
        )
        return ContextBundle.empty(user_id=user_id, intent=intent)

    bundle = ContextBundle.from_edges(user_id=user_id, intent=intent, edges=edges)

    # Optional post-filter: drop kinds that aren't relevant for this intent.
    keep = tuple(kinds) if kinds else RELEVANT_BY_INTENT.get(intent, ())
    if keep:
        bundle.by_kind = {k: v for k, v in bundle.by_kind.items() if k in keep}
    return bundle


# ---------------------------------------------------------------- Helpers


# Maps entity-type names to short human labels used in `to_prompt`.
_PRETTY_LABEL: Mapping[str, str] = {
    "Allergy": "Allergies",
    "DietaryRestriction": "Dietary restrictions",
    "HealthCondition": "Health conditions",
    "FoodPreference": "Food preferences",
    "CulturalContext": "Cultural context",
    "RestaurantVisit": "Past visits",
}


# Heuristic mapping from edge metadata back to entity-type names.
# Graphiti edges carry the source node's labels in their `.attributes`
# dict and the relationship name in `.name`; both can hint at the kind.
def _classify_edge(edge: EntityEdge) -> str:
    """Best-effort classification of an EntityEdge into one of our entity types.

    Falls back to "Other" if no signal matches. Keep this conservative —
    misclassification just shifts a fact into a less-pretty bucket; the
    facts are still in ``bundle.facts`` regardless.
    """
    candidates = []

    # `attributes` may carry typed entity payload from extraction.
    attrs = getattr(edge, "attributes", None) or {}
    if isinstance(attrs, dict):
        for key in ("entity_type", "type", "kind", "label"):
            v = attrs.get(key)
            if isinstance(v, str):
                candidates.append(v)

    # The edge name itself sometimes encodes the entity type.
    if edge.name:
        candidates.append(edge.name)

    for c in candidates:
        norm = c.strip()
        for known in (
            "Allergy",
            "DietaryRestriction",
            "HealthCondition",
            "FoodPreference",
            "CulturalContext",
            "RestaurantVisit",
        ):
            if known.lower() in norm.lower():
                return known
    return "Other"
