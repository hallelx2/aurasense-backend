"""Phase 0 import-smoke tests.

These exist purely to assert that the backend's modules can be imported
without raising. Until we have real integration tests, this is the gate the
CI workflow relies on to refuse a deploy if the codebase is broken.
"""

from __future__ import annotations

import importlib

import pytest


# Modules that should always load cleanly. Add new ones here as the
# refactor progresses; deletions/renames will surface as failures.
_MODULES = [
    "src.app.core.config",
    "src.app.core.security",
    "src.app.api.routes.onboarding_ws",
    "src.app.models.session",
    "src.app.models.user",
    "src.app.models.relationships",
    # Phase-1 additions:
    "src.app.services.llm_gateway",
    "src.agents.base",
    "src.agents.base.state",
    "src.agents.base.agent",
    "src.agents.base.checkpointer",
    "src.agents.base.collaboration",
    "src.agents.onboarding_agent.graph",
    "src.agents.onboarding_agent.state",
    # Phase-2 additions:
    "src.app.services.graphiti",
    "src.app.services.graphiti.client",
    "src.app.services.graphiti.contract",
    "src.app.services.graphiti.retriever",
    "src.app.services.graphiti.entity_types",
    "src.agents.onboarding_agent.agent",
    # Phase-1.5 polish:
    "src.app.core.logging",
    # Phase-3 additions:
    "src.agents.profile_agent",
    "src.agents.profile_agent.snapshot",
    "src.agents.profile_agent.state",
    "src.agents.profile_agent.graph",
    "src.agents.profile_agent.agent",
    "src.app.services.profile_service",
    "src.app.services.social_service",
    "src.app.services.travel_service",
    "src.app.api.routes.users",
]


@pytest.mark.parametrize("module", _MODULES)
def test_module_imports_cleanly(module: str) -> None:
    importlib.import_module(module)


def test_settings_loads_in_dev() -> None:
    """Sanity: the new pydantic-settings model loads without explosions in dev."""
    from src.app.core.config import settings

    assert settings.ENVIRONMENT == "development"
    assert settings.PORT == 8000
    # DATABASE_URL is a derived property; make sure it composes correctly.
    assert settings.DATABASE_URL.startswith("bolt://")


def test_production_refuses_placeholder_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Boot must fail loud if prod is configured with placeholder secrets."""
    from src.app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "your-secret-key-change-this")
    monkeypatch.setenv("NEO4J_PASSWORD", "test1234")
    monkeypatch.setenv("GROQ_API_KEY", "")

    with pytest.raises(Exception) as exc_info:
        Settings()

    msg = str(exc_info.value)
    assert "SECRET_KEY" in msg
    assert "NEO4J_PASSWORD" in msg
    assert "GROQ_API_KEY" in msg


def test_production_accepts_real_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "real-prod-secret-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    monkeypatch.setenv("NEO4J_PASSWORD", "a-real-strong-password-9!aZ")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_real_key_here")

    s = Settings()
    assert s.is_production is True
