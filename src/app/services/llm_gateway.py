"""
LLM Gateway — single chokepoint for every LLM call in the system.

Agents, the supervisor, and Graphiti all obtain their model client through
``gateway.get_llm(role)``. Roles are resolved to a ``provider:model`` profile
via the env-driven settings (``LLM_PROFILE_<ROLE>`` with fall-back to
``LLM_PROFILE_DEFAULT``).

Adding a provider = one branch in :py:meth:`LLMGateway._build` plus its
env-var key in ``Settings``. Adding a role = register it in
``Settings.LLM_ROLES`` and (optionally) add an ``LLM_PROFILE_<ROLE>``
field — the gateway reads via ``settings.llm_profile_for(role)``.

This file deliberately does **not** import ``langchain_anthropic``,
``langchain_groq``, etc. at module level — they're imported inside the
match arms so a missing optional dep never breaks unrelated paths.
"""

from __future__ import annotations

import logging
from typing import Dict

from langchain_core.language_models import BaseChatModel

from src.app.core.config import settings

logger = logging.getLogger(__name__)


class LLMGateway:
    """Resolves a role to a ``BaseChatModel`` and caches the result.

    The cache key is the *role* (not the spec) so changing
    ``LLM_PROFILE_FOOD`` between two boots picks up cleanly.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, BaseChatModel] = {}

    # ----------------------------------------------------- public API

    def get_llm(self, role: str) -> BaseChatModel:
        """Return a chat model for ``role``. Cached for the process lifetime."""
        if role in self._cache:
            return self._cache[role]
        spec = settings.llm_profile_for(role)
        llm = self._build(spec, role=role)
        self._cache[role] = llm
        logger.info("LLM gateway: role=%s resolved to %s", role, spec)
        return llm

    def reset_cache(self) -> None:
        """Drop the cache (useful in tests after monkeypatching env vars)."""
        self._cache.clear()

    # --------------------------------------------------- builder helpers

    def _build(self, spec: str, *, role: str) -> BaseChatModel:
        provider, _, model = spec.partition(":")
        if not provider or not model:
            # Settings._validate_llm_profiles should already have caught
            # this; defense in depth.
            raise ValueError(
                f"LLM profile for role {role!r} must be 'provider:model', "
                f"got {spec!r}"
            )

        if provider == "groq":
            from langchain_groq import ChatGroq

            return ChatGroq(model=model, api_key=settings.GROQ_API_KEY)

        if provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=model, api_key=settings.OPENAI_API_KEY)

        if provider == "ollama":
            from langchain_openai import ChatOpenAI

            # Ollama exposes an OpenAI-compatible API at `/v1`.
            return ChatOpenAI(
                model=model,
                api_key="ollama",  # ollama ignores the key but the SDK insists
                base_url=settings.OLLAMA_BASE_URL,
            )

        if provider == "openrouter":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model,
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
            )

        if provider == "gemini":
            # Google's Gemini speaks OpenAI-compatible at GEMINI_BASE_URL.
            # Pass GEMINI_API_KEY as the bearer key.
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model,
                api_key=settings.GEMINI_API_KEY,
                base_url=settings.GEMINI_BASE_URL,
            )

        raise ValueError(
            f"LLM gateway: unknown provider {provider!r} for role {role!r}. "
            f"Known: {sorted(settings.LLM_KNOWN_PROVIDERS)}"
        )


# Module-level singleton. Import as `from src.app.services.llm_gateway import gateway`.
gateway = LLMGateway()
