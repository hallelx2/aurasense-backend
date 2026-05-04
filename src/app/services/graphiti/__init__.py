"""
Graphiti integration package.

Public API:

* ``get_graphiti()`` / ``setup_graphiti()`` / ``close_graphiti()`` — the
  process-shared client.
* ``contract`` module — write-side helpers (record_user_utterance,
  record_extracted_facts, record_recommendation, record_visit).
* ``retriever`` module — read-side helpers (get_relevant_context,
  ContextBundle).
* ``entity_types`` — Pydantic models Graphiti uses for typed extraction.
"""

from .client import (
    close_graphiti,
    get_graphiti,
    reset_graphiti_cache,
    setup_graphiti,
)
from .entity_types import ENTITY_TYPES, RELEVANT_BY_INTENT

__all__ = [
    "ENTITY_TYPES",
    "RELEVANT_BY_INTENT",
    "close_graphiti",
    "get_graphiti",
    "reset_graphiti_cache",
    "setup_graphiti",
]
