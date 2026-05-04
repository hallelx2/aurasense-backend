"""
Graphiti write contract — the only place agents call to persist memory.

Why a contract module instead of agents calling `graphiti.add_episode`
directly: episode body shape (JSON-encoded payload) and metadata
conventions (`event_type`, `agent_name`, `reference_time`, `group_id =
user_id`) need to stay consistent so the read side
(`retriever.get_relevant_context`) and entity-type extraction work
predictably. Centralizing here also gives us one place to add tracing,
sampling, and dead-letter handling later.

Every function:
- Scopes the episode by ``group_id = user_id`` so multi-user reads stay
  isolated (the README's "personalization across sessions" guarantee
  depends on this).
- Sets ``reference_time = datetime.utcnow()`` so search time-decay works.
- Passes ``entity_types`` from ``entity_types.ENTITY_TYPES`` so the LLM
  recognizes domain types when it extracts.
- Catches and logs Graphiti errors (write failures must NOT break the
  user-facing flow — agents should still respond even if memory failed).

Callers should treat all returns as fire-and-forget unless they need the
``AddEpisodeResults`` for follow-up correlations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from graphiti_core.nodes import EpisodeType

from .client import get_graphiti
from .entity_types import ENTITY_TYPES

logger = logging.getLogger(__name__)


# Default `entity_types` payload passed to every episode write. Subset
# overrides allowed via the ``entity_types`` kwarg on individual calls.
_DEFAULT_ENTITY_TYPES = ENTITY_TYPES


# ---------------------------------------------------------------- Internals


async def _add_episode(
    *,
    user_id: str,
    name: str,
    episode_body: str,
    source: EpisodeType,
    source_description: str,
    entity_types: Optional[Mapping[str, type]] = None,
) -> Optional[Any]:
    """Inner helper. Logs and swallows write errors (never raises to caller)."""
    try:
        g = get_graphiti()
        return await g.add_episode(
            name=name,
            episode_body=episode_body,
            source=source,
            source_description=source_description,
            reference_time=datetime.utcnow(),
            group_id=user_id,
            entity_types=dict(entity_types or _DEFAULT_ENTITY_TYPES),
        )
    except Exception:
        # Memory write must not break the user-facing flow.
        logger.exception(
            "graphiti.add_episode failed for user_id=%s name=%s", user_id, name
        )
        return None


# ---------------------------------------------------- Public write helpers


async def record_user_utterance(
    user_id: str,
    transcript: str,
    *,
    agent_name: str,
) -> Optional[Any]:
    """Record a raw user utterance (post-STT) so prior turns are searchable.

    Stored with ``EpisodeType.message`` so Graphiti treats it as
    conversational — entity extraction picks up names, allergies, prefs
    mentioned in passing.
    """
    if not transcript:
        return None
    return await _add_episode(
        user_id=user_id,
        name=f"{agent_name}-utterance",
        episode_body=transcript,
        source=EpisodeType.message,
        source_description=f"{agent_name}_agent.user_turn",
    )


async def record_extracted_facts(
    user_id: str,
    facts: Mapping[str, Any],
    *,
    agent_name: str,
) -> Optional[Any]:
    """Record structured facts an agent's extractor pulled from a turn.

    The episode body is the JSON of ``facts`` so Graphiti can extract
    typed entities directly from the structured content.
    """
    if not facts:
        return None
    return await _add_episode(
        user_id=user_id,
        name=f"{agent_name}-facts",
        episode_body=json.dumps({"extracted": _jsonable(facts)}, default=str),
        source=EpisodeType.json,
        source_description=f"{agent_name}_agent.extraction",
    )


async def record_recommendation(
    user_id: str,
    *,
    agent_name: str,
    recommendation: Mapping[str, Any],
    accepted: Optional[bool] = None,
) -> Optional[Any]:
    """Record an agent's recommendation + (optional) user acceptance."""
    body = {
        "recommendation": _jsonable(recommendation),
        "accepted": accepted,
    }
    return await _add_episode(
        user_id=user_id,
        name=f"{agent_name}-recommendation",
        episode_body=json.dumps(body, default=str),
        source=EpisodeType.json,
        source_description=f"{agent_name}_agent.recommendation",
    )


async def record_visit(
    user_id: str,
    *,
    restaurant: str,
    visit_data: Optional[Mapping[str, Any]] = None,
    agent_name: str = "food",
) -> Optional[Any]:
    """Record a confirmed visit / order at a restaurant."""
    body = {
        "restaurant": restaurant,
        "data": _jsonable(visit_data or {}),
    }
    return await _add_episode(
        user_id=user_id,
        name=f"{agent_name}-visit",
        episode_body=json.dumps(body, default=str),
        source=EpisodeType.json,
        source_description=f"{agent_name}_agent.visit",
    )


# ------------------------------------------- Lightweight back-compat aliases
# (memory_service.py used to write events; let it route through here.)


async def record_user_event(
    user_id: str,
    event_type: str,
    *,
    payload: Optional[Mapping[str, Any]] = None,
    agent_name: str = "auth",
) -> Optional[Any]:
    """Record an audit-style event (e.g. registration, login).

    Used by ``memory_service`` for back-compat. Prefer the more specific
    helpers above when adding new write sites.
    """
    body = {"event_type": event_type, "data": _jsonable(payload or {})}
    return await _add_episode(
        user_id=user_id,
        name=f"{agent_name}-{event_type}",
        episode_body=json.dumps(body, default=str),
        source=EpisodeType.json,
        source_description=f"{agent_name}.{event_type}",
    )


# ---------------------------------------------------------------- Helpers


def _jsonable(value: Any) -> Any:
    """Make a value safe for `json.dumps` via the default=str fallback.

    Dates, neomodel nodes, etc. all coerce cleanly with default=str —
    this is here mainly to drop pydantic v2 model instances down to dicts.
    """
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Mapping):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return value
