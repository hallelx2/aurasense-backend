"""
UserContextSnapshot — the structured payload every other agent reads
through ``profile_service.get_user_context(user_id, intent=...)``.

It is the ONE shape the food/travel/social agents (and frontend
personalization cards via the REST endpoint) consume — keeping a stable
schema here means the consumers don't need to re-implement Neo4j +
Graphiti merge logic, and we have one place to evolve as new fact
types come online.

Two layers of data:

* ``profile`` — canonical, structured properties from the ``User``
  neomodel node. These are the user's *declared* facts (set during
  onboarding, edited via /users/me/...).
* ``graph_context`` — fuzzy, evolving facts retrieved from Graphiti via
  the retriever. These are what the user has *said* (or what other
  agents have *observed*) over time. They expire / shift with use.

The convenience accessors (``allergies``, ``cuisines_liked``, ...)
combine both layers so consumers don't need to dedupe / merge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class UserContextSnapshot:
    """All the personalization context an agent needs about a user."""

    user_id: str
    intent: str

    # --- Layer 1: canonical neomodel `User` properties ------------------
    profile: Dict[str, Any] = field(default_factory=dict)

    # --- Layer 2: Graphiti `ContextBundle.to_dict()` --------------------
    graph_context: Dict[str, Any] = field(default_factory=dict)

    # --- Convenience flat lists merged from both layers -----------------
    allergies: List[str] = field(default_factory=list)
    dietary_restrictions: List[str] = field(default_factory=list)
    cuisines_liked: List[str] = field(default_factory=list)
    cultural_background: List[str] = field(default_factory=list)
    health_conditions: List[str] = field(default_factory=list)

    # --- Recent activity ------------------------------------------------
    recent_visits: List[Dict[str, Any]] = field(default_factory=list)

    # --- Onboarding state -----------------------------------------------
    is_onboarded: bool = False

    # ---------------------------------------------------- Serialization

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable form, used as the REST response body."""
        return {
            "user_id": self.user_id,
            "intent": self.intent,
            "profile": dict(self.profile),
            "graph_context": dict(self.graph_context),
            "allergies": list(self.allergies),
            "dietary_restrictions": list(self.dietary_restrictions),
            "cuisines_liked": list(self.cuisines_liked),
            "cultural_background": list(self.cultural_background),
            "health_conditions": list(self.health_conditions),
            "recent_visits": list(self.recent_visits),
            "is_onboarded": self.is_onboarded,
        }

    def to_prompt(self) -> str:
        """Render as a clean text block for LLM prompt injection.

        Specialist agents (food, travel) embed this verbatim in their
        system prompts so the model sees the complete personalization
        context in one structured chunk.
        """
        if not any(
            (
                self.allergies,
                self.dietary_restrictions,
                self.cuisines_liked,
                self.cultural_background,
                self.health_conditions,
            )
        ):
            return "(No prior personalization context known about the user yet.)"

        lines: list[str] = []
        if self.allergies:
            lines.append(f"- Allergies: {', '.join(sorted(set(self.allergies)))}")
        if self.dietary_restrictions:
            lines.append(
                f"- Dietary restrictions: {', '.join(sorted(set(self.dietary_restrictions)))}"
            )
        if self.health_conditions:
            lines.append(
                f"- Health conditions: {', '.join(sorted(set(self.health_conditions)))}"
            )
        if self.cuisines_liked:
            lines.append(
                f"- Cuisine preferences: {', '.join(sorted(set(self.cuisines_liked)))}"
            )
        if self.cultural_background:
            lines.append(
                f"- Cultural background: {', '.join(sorted(set(self.cultural_background)))}"
            )
        if self.recent_visits:
            visit_summaries = [
                v.get("restaurant", "(unknown)") for v in self.recent_visits[:3]
            ]
            lines.append(f"- Recent visits: {', '.join(visit_summaries)}")
        return "\n".join(lines)

    # ---------------------------------------------------- Construction

    @classmethod
    def empty(cls, user_id: str, intent: str) -> "UserContextSnapshot":
        return cls(user_id=user_id, intent=intent)

    @classmethod
    def from_user_and_graph(
        cls,
        *,
        user_id: str,
        intent: str,
        user: Optional[Any],
        graph_context: Dict[str, Any],
        recent_visits: Optional[List[Dict[str, Any]]] = None,
    ) -> "UserContextSnapshot":
        """Merge a neomodel User row + a Graphiti ContextBundle.to_dict() output.

        Args:
            user_id: canonical user id (User.uid).
            intent: the calling agent's intent ("food", "travel", "profile", ...).
            user: the loaded ``User`` neomodel node, or ``None`` if not found.
            graph_context: dict from ``ContextBundle.to_dict()``.
            recent_visits: optional pre-loaded recent visit edges.
        """
        snapshot = cls(user_id=user_id, intent=intent)
        snapshot.graph_context = dict(graph_context or {})
        snapshot.recent_visits = list(recent_visits or [])

        # Layer 2 — graph-derived facts. Always populated, even when no
        # User node exists yet (caller may be querying a non-onboarded
        # user; we still want to surface anything Graphiti knows).
        graph_by_kind: Dict[str, List[str]] = (
            graph_context.get("by_kind", {}) if graph_context else {}
        )

        # Layer 1 — canonical User properties (only available when a
        # neomodel node was found).
        if user is None:
            canonical_allergies: List[str] = []
            canonical_dietary: List[str] = []
            canonical_cuisines: List[str] = []
            canonical_culture: List[str] = []
        else:
            profile_fields = (
                "first_name",
                "last_name",
                "username",
                "email",
                "phone",
                "age",
                "price_range",
                "is_tourist",
                "is_onboarded",
                "preferred_languages",
                "spice_tolerance",
            )
            snapshot.profile = {
                field_name: getattr(user, field_name, None)
                for field_name in profile_fields
            }
            snapshot.is_onboarded = bool(getattr(user, "is_onboarded", False))

            canonical_allergies = list(getattr(user, "food_allergies", None) or [])
            canonical_dietary = list(getattr(user, "dietary_restrictions", None) or [])
            canonical_cuisines = list(getattr(user, "cuisine_preferences", None) or [])
            canonical_culture = list(getattr(user, "cultural_background", None) or [])

        # Combined flat lists: prefer canonical (Layer 1 first), then
        # merge in Graphiti-derived facts (Layer 2) that aren't already
        # represented (case-insensitive dedupe).
        snapshot.allergies = _merge_unique(
            canonical_allergies, graph_by_kind.get("Allergy", [])
        )
        snapshot.dietary_restrictions = _merge_unique(
            canonical_dietary, graph_by_kind.get("DietaryRestriction", [])
        )
        snapshot.cuisines_liked = _merge_unique(
            canonical_cuisines, graph_by_kind.get("FoodPreference", [])
        )
        snapshot.cultural_background = _merge_unique(
            canonical_culture, graph_by_kind.get("CulturalContext", [])
        )
        # Health conditions are graph-only for now (User node has no
        # column — they're typed-extracted from utterances).
        snapshot.health_conditions = list(graph_by_kind.get("HealthCondition", []))

        return snapshot


# --------------------------------------------------------- helpers


def _merge_unique(*sources: List[str]) -> List[str]:
    """Concatenate string lists preserving first-seen order, case-insensitive dedupe."""
    seen: set[str] = set()
    out: List[str] = []
    for src in sources:
        for item in src:
            if not isinstance(item, str):
                continue
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out
