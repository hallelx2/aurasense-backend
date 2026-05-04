"""Unit tests for the LLM gateway and the LLM profile validator."""

from __future__ import annotations

import importlib

import pytest


def _fresh_settings_module():
    """Re-import config so monkeypatched env vars are picked up.

    Also reloads `llm_gateway`, otherwise its `from .config import settings`
    binding still points at the previous (stale) Settings instance and
    role profile lookups read the wrong env.
    """
    import src.app.core.config as config_mod
    import src.app.services.llm_gateway as gw_mod

    importlib.reload(config_mod)
    importlib.reload(gw_mod)
    return config_mod


def test_default_role_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LLM_PROFILE_DEFAULT", "groq:llama-3.3-70b-versatile")
    monkeypatch.delenv("LLM_PROFILE_FOOD", raising=False)

    config_mod = _fresh_settings_module()
    assert (
        config_mod.settings.llm_profile_for("food")
        == "groq:llama-3.3-70b-versatile"
    )


def test_role_specific_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LLM_PROFILE_DEFAULT", "groq:llama-3.3-70b-versatile")
    monkeypatch.setenv("LLM_PROFILE_FOOD", "openai:gpt-4o-mini")

    config_mod = _fresh_settings_module()
    assert config_mod.settings.llm_profile_for("food") == "openai:gpt-4o-mini"
    assert (
        config_mod.settings.llm_profile_for("supervisor")
        == "groq:llama-3.3-70b-versatile"
    )


def test_unknown_role_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LLM_PROFILE_DEFAULT", "groq:llama-3.3-70b-versatile")

    config_mod = _fresh_settings_module()
    assert (
        config_mod.settings.llm_profile_for("not-a-real-role")
        == "groq:llama-3.3-70b-versatile"
    )


def test_typoed_provider_refused_at_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    """`grok:` (typo) must surface as a startup error, not a 500 at runtime."""
    from src.app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LLM_PROFILE_FOOD", "grok:llama-3.3-70b")

    with pytest.raises(Exception) as exc:
        Settings()

    assert "grok" in str(exc.value)
    assert "unknown provider" in str(exc.value)


def test_malformed_profile_refused_at_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LLM_PROFILE_FOOD", "no-colon-here")

    with pytest.raises(Exception) as exc:
        Settings()

    assert "provider:model" in str(exc.value)


def test_gateway_caches_per_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling get_llm twice with the same role should return the same object."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROFILE_DEFAULT", "groq:llama-3.3-70b-versatile")

    _fresh_settings_module()
    from src.app.services.llm_gateway import LLMGateway

    g = LLMGateway()
    a = g.get_llm("food")
    b = g.get_llm("food")
    assert a is b


def test_gateway_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """If somehow a bad spec slips past Settings validation, the gateway
    still refuses to build it."""
    from src.app.services.llm_gateway import LLMGateway

    g = LLMGateway()
    with pytest.raises(ValueError, match="unknown provider"):
        g._build("not-a-provider:gpt-4", role="food")


def test_groq_role_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("LLM_PROFILE_FOOD", "groq:llama-3.3-70b-versatile")

    _fresh_settings_module()
    from src.app.services.llm_gateway import LLMGateway

    llm = LLMGateway().get_llm("food")
    # Don't make a real API call; just confirm we got a langchain chat model.
    from langchain_core.language_models import BaseChatModel

    assert isinstance(llm, BaseChatModel)


def test_openai_role_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("LLM_PROFILE_AGENT", "openai:gpt-4o-mini")

    _fresh_settings_module()
    from src.app.services.llm_gateway import LLMGateway

    llm = LLMGateway().get_llm("agent")
    from langchain_core.language_models import BaseChatModel

    assert isinstance(llm, BaseChatModel)


def test_gemini_role_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gemini speaks OpenAI-compatible at GEMINI_BASE_URL — gateway handles it."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("LLM_PROFILE_FOOD", "gemini:gemini-2.0-flash")

    _fresh_settings_module()
    from src.app.services.llm_gateway import LLMGateway

    llm = LLMGateway().get_llm("food")
    from langchain_core.language_models import BaseChatModel
    from langchain_openai import ChatOpenAI

    assert isinstance(llm, BaseChatModel)
    # Specifically a ChatOpenAI under the hood — confirms the OpenAI-compat path.
    assert isinstance(llm, ChatOpenAI)


def test_gemini_typo_refused_at_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    """`gemni:` (missing 'i') must surface as a startup error."""
    from src.app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LLM_PROFILE_AGENT", "gemni:gemini-2.0-flash")

    with pytest.raises(Exception) as exc:
        Settings()

    assert "gemni" in str(exc.value)
    assert "unknown provider" in str(exc.value)
