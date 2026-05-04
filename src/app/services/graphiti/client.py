"""
Graphiti client facade.

Wraps `graphiti_core.Graphiti` as a process-singleton so every agent and
service uses the same instance (one Neo4j connection pool, one LLM
client, one embedder). The standalone `zepai/graphiti` Docker container
is no longer used; Graphiti runs inside the FastAPI process.

LLM + embedder choice is driven by settings:
  - GRAPHITI_LLM_PROVIDER  (gemini | openai | groq)
  - GRAPHITI_LLM_MODEL
  - GRAPHITI_EMBEDDER_PROVIDER  (gemini | openai)
  - GRAPHITI_EMBEDDER_MODEL
  - GRAPHITI_EMBEDDER_DIM

Groq has no embeddings endpoint, so `GRAPHITI_EMBEDDER_PROVIDER=groq` is
rejected at construction. The validator surfaces the problem at boot
(via the lifespan hook) rather than at first episode write.

Public API used by the rest of the codebase lives in `contract.py`
(writes) and `retriever.py` (reads). Direct callers of `get_graphiti()`
should be rare and limited to admin / migration scripts.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.embedder import OpenAIEmbedder
from graphiti_core.embedder.openai import OpenAIEmbedderConfig
from graphiti_core.llm_client import LLMConfig, OpenAIClient

from src.app.core.config import settings

logger = logging.getLogger(__name__)


_VALID_LLM_PROVIDERS = {"gemini", "openai", "groq"}
_VALID_EMBEDDER_PROVIDERS = {"gemini", "openai"}  # groq has no embeddings


# ---------------------------------------------------------------- Builders


def _build_llm_client() -> OpenAIClient:
    """Build the `OpenAIClient` Graphiti will use for entity extraction.

    All three supported providers (gemini, openai, groq) speak
    OpenAI-compatible chat completions, so we always use `OpenAIClient`
    and just swap `base_url` + `api_key` accordingly.
    """
    provider = settings.GRAPHITI_LLM_PROVIDER.lower()
    if provider not in _VALID_LLM_PROVIDERS:
        raise ValueError(
            f"GRAPHITI_LLM_PROVIDER={provider!r} is invalid; "
            f"choose one of {sorted(_VALID_LLM_PROVIDERS)}"
        )

    api_key, base_url = _llm_credentials_for(provider)
    if not api_key:
        raise RuntimeError(
            f"GRAPHITI_LLM_PROVIDER={provider!r} but the matching API key "
            f"is empty (see settings)."
        )

    config = LLMConfig(
        api_key=api_key,
        model=settings.GRAPHITI_LLM_MODEL,
        base_url=base_url,
        # graphiti-core defaults are sane; we only override max_tokens to
        # keep extraction passes from blowing the context budget.
        max_tokens=8192,
    )
    return OpenAIClient(config=config)


def _build_cross_encoder() -> OpenAIRerankerClient:
    """Build the search-result reranker.

    Graphiti's default reranker is OpenAI-only and crashes on import if
    `OPENAI_API_KEY` is empty (as is the case when the user picks Gemini
    or Groq+OpenAI-embed). We side-step that by constructing the
    reranker explicitly with the SAME LLM config the agent extractor
    uses — every supported provider exposes chat completions, which is
    all the reranker needs.
    """
    provider = settings.GRAPHITI_LLM_PROVIDER.lower()
    api_key, base_url = _llm_credentials_for(provider)
    config = LLMConfig(
        api_key=api_key,
        # Reranker uses a smaller model when available; reuse the main
        # one if no small alternative is configured.
        model=settings.GRAPHITI_LLM_MODEL,
        base_url=base_url,
    )
    return OpenAIRerankerClient(config=config)


def _build_embedder() -> OpenAIEmbedder:
    """Build the `OpenAIEmbedder` Graphiti will use for semantic search."""
    provider = settings.GRAPHITI_EMBEDDER_PROVIDER.lower()
    if provider not in _VALID_EMBEDDER_PROVIDERS:
        raise ValueError(
            f"GRAPHITI_EMBEDDER_PROVIDER={provider!r} is invalid; "
            f"groq has no embeddings endpoint. Choose one of "
            f"{sorted(_VALID_EMBEDDER_PROVIDERS)}"
        )

    api_key, base_url = _embedder_credentials_for(provider)
    if not api_key:
        raise RuntimeError(
            f"GRAPHITI_EMBEDDER_PROVIDER={provider!r} but the matching API "
            f"key is empty."
        )

    config = OpenAIEmbedderConfig(
        api_key=api_key,
        embedding_model=settings.GRAPHITI_EMBEDDER_MODEL,
        embedding_dim=settings.GRAPHITI_EMBEDDER_DIM,
        base_url=base_url,
    )
    return OpenAIEmbedder(config=config)


def _llm_credentials_for(provider: str) -> tuple[str, Optional[str]]:
    """Return (api_key, base_url) for the LLM side."""
    if provider == "gemini":
        return settings.GEMINI_API_KEY, settings.GEMINI_BASE_URL
    if provider == "openai":
        return settings.OPENAI_API_KEY, None  # SDK default api.openai.com/v1
    if provider == "groq":
        return settings.GROQ_API_KEY, "https://api.groq.com/openai/v1"
    raise AssertionError("unreachable")  # _VALID_LLM_PROVIDERS guards this


def _embedder_credentials_for(provider: str) -> tuple[str, Optional[str]]:
    """Return (api_key, base_url) for the embedder side."""
    if provider == "gemini":
        return settings.GEMINI_API_KEY, settings.GEMINI_BASE_URL
    if provider == "openai":
        return settings.OPENAI_API_KEY, None
    raise AssertionError("unreachable")


# -------------------------------------------------------- Singleton accessor


@lru_cache(maxsize=1)
def get_graphiti() -> Graphiti:
    """Return the process-shared `Graphiti` instance.

    Construction is lazy + cached. Call `setup_graphiti()` once at app
    startup so indices/constraints are created before any episode writes
    or searches run.
    """
    llm_client = _build_llm_client()
    embedder = _build_embedder()
    cross_encoder = _build_cross_encoder()
    g = Graphiti(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder,
    )
    logger.info(
        "Graphiti SDK initialized: llm=%s:%s embedder=%s:%s (dim=%d)",
        settings.GRAPHITI_LLM_PROVIDER,
        settings.GRAPHITI_LLM_MODEL,
        settings.GRAPHITI_EMBEDDER_PROVIDER,
        settings.GRAPHITI_EMBEDDER_MODEL,
        settings.GRAPHITI_EMBEDDER_DIM,
    )
    return g


async def setup_graphiti() -> None:
    """One-time index + constraint setup. Idempotent."""
    g = get_graphiti()
    await g.build_indices_and_constraints()
    logger.info("Graphiti indices + constraints built")


async def close_graphiti() -> None:
    """Close the underlying Neo4j driver (called from FastAPI lifespan shutdown)."""
    if get_graphiti.cache_info().currsize == 0:
        return
    g = get_graphiti()
    try:
        await g.close()
    except Exception:
        logger.exception("Error closing Graphiti client")
    finally:
        get_graphiti.cache_clear()


def reset_graphiti_cache() -> None:
    """Drop the cached singleton (used in tests that swap settings)."""
    get_graphiti.cache_clear()


# ------------------------------------------------- Backward-compat aliases

# The old `Client` class is gone, but `services.graphiti.__init__` may
# still re-export it. We expose `get_graphiti()` as the canonical entry.
Client = None  # type: ignore[assignment]  # explicit "removed"
