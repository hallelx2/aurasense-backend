"""Shared pytest configuration for the backend test suite.

Sets safe defaults for env vars BEFORE the application's settings module is
imported, so test runs don't accidentally trip the production-safety asserts
or try to dial real Neo4j/Redis instances during import-time work.
"""

from __future__ import annotations

import os


def _ensure_dev_env() -> None:
    # Force dev mode so the production-secret asserts in config.py don't
    # fire during a test-time `import src.app.main`.
    os.environ.setdefault("ENVIRONMENT", "development")
    # Provide harmless non-empty defaults; tests that need real values can
    # override via monkeypatch.setenv.
    os.environ.setdefault("SECRET_KEY", "test-secret-not-for-prod")
    os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
    os.environ.setdefault("NEO4J_PASSWORD", "test-neo4j-password")


_ensure_dev_env()
