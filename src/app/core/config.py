"""
Application Settings.

Loaded from environment variables via `pydantic-settings`. Production boot
is hard-stopped on placeholder / well-known secrets so a misconfigured deploy
can never silently ship with the public defaults.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Sentinels that must never appear in production. If they do, boot fails.
_PLACEHOLDER_SECRET_KEY = "your-secret-key-change-this"
_PLACEHOLDER_NEO4J_PASSWORDS: set[str] = {"test1234", "neo4j", "password", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------ App
    APP_NAME: str = "Aurasense"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8000, validation_alias="APP_PORT")
    LOG_LEVEL: str = "INFO"

    # ----------------------------------------------------------------- CORS
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
        ]
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "*"
    CORS_ALLOW_HEADERS: str = "*"

    PRODUCTION_DOMAIN: str = ""
    FRONTEND_URL: str = "http://localhost:3000"

    # --------------------------------------------------------------- Neo4j
    NEO4J_HOST: str = "localhost"
    NEO4J_PORT: int = Field(default=7687, validation_alias="NEO4J_BOLT_PORT")
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "test1234"
    # If unset, computed in `_compute_neo4j_uri` from host/port.
    NEO4J_URI: Optional[str] = None

    # --------------------------------------------------------------- Redis
    REDIS_URL: str = "redis://localhost:6379"

    # ----------------------------------------------------- Provider keys
    GROQ_API_KEY: str = ""
    GOOGLE_PLACES_API_KEY: str = ""
    FOURSQUARE_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    # Gemini speaks OpenAI-compatible at this base URL; pass GEMINI_API_KEY
    # in the Authorization header just like a normal OpenAI key.
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # ----------------------------------------------------- MCP / food data
    # Which restaurant-data provider the food agent uses.
    #   "mock"        — bundled 12-dish catalog (best for testing the
    #                   allergy-safety flow because it has explicit
    #                   ingredient lists; default).
    #   "foursquare"  — real restaurants via Foursquare Places API v3.
    #                   Requires FOURSQUARE_API_KEY. Returns restaurant
    #                   discovery only (no per-dish ingredients), so
    #                   allergy filtering is weaker.
    MCP_PROVIDER: str = "mock"
    FOURSQUARE_BASE_URL: str = "https://api.foursquare.com/v3"

    # -------------------------------------------------------- Cloud storage
    CLOUD_STORAGE_PROVIDER: str = "aws"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AUDIO_BUCKET_NAME: str = "aurasense-audio-files"

    MAX_AUDIO_FILE_SIZE_MB: int = 10
    AUDIO_PROCESSING_TIMEOUT: int = 30

    # -------------------------------------------------------- Auth / JWT
    SECRET_KEY: str = _PLACEHOLDER_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ----------------------------------------------------------- Graphiti
    # NOTE (Phase 2): the standalone `zepai/graphiti` Docker container is
    # gone. Graphiti now runs in-process via `graphiti-core` and writes
    # directly to the same Neo4j database as the rest of the app.
    # GRAPHITI_HOST/PORT/URL are retained as deprecated no-ops in case
    # anything still imports them; nothing in the code path uses them.
    GRAPHITI_HOST: str = "localhost"
    GRAPHITI_PORT: int = 8080
    GRAPHITI_URL: str = "http://localhost:8080"

    # In-process Graphiti config — pick the LLM + embedder Graphiti will
    # use for episode entity extraction and semantic search. Defaults are
    # Gemini (single-key, free tier) because we have a Gemini key handy
    # and OpenAI's pricing is not free.
    #
    # Provider must be one of: "gemini", "openai", "groq" (LLM only — Groq
    # has no embeddings; the embedder must be a different provider).
    GRAPHITI_LLM_PROVIDER: str = "gemini"
    GRAPHITI_LLM_MODEL: str = "gemini-2.0-flash"

    GRAPHITI_EMBEDDER_PROVIDER: str = "gemini"
    GRAPHITI_EMBEDDER_MODEL: str = "text-embedding-004"
    GRAPHITI_EMBEDDER_DIM: int = 768  # 768 for Gemini, 1536 for OpenAI text-embedding-3-small

    # -------------------------------------------------------- LLM gateway
    # Every agent / service obtains its model via the LLM gateway, which
    # resolves a role (e.g. "food", "supervisor", "graphiti") to a profile
    # string of the form "provider:model". A role with an empty / unset
    # profile falls back to LLM_PROFILE_DEFAULT.
    LLM_PROFILE_DEFAULT: str = "groq:llama-3.3-70b-versatile"

    # Per-role overrides. Add new roles by registering them in
    # `LLM_ROLES` below; pydantic-settings will pick up the env var
    # `LLM_PROFILE_<UPPER_ROLE>` automatically.
    #
    # NOTE: Graphiti's LLM is configured separately via
    # GRAPHITI_LLM_PROVIDER / GRAPHITI_LLM_MODEL — graphiti-core needs an
    # OpenAI-style client object, not a LangChain BaseChatModel, so it
    # doesn't go through the gateway.
    LLM_PROFILE_AGENT: str = ""
    LLM_PROFILE_SUPERVISOR: str = ""
    LLM_PROFILE_ONBOARDING: str = ""
    LLM_PROFILE_FOOD: str = ""
    LLM_PROFILE_PROFILE: str = ""
    LLM_PROFILE_TRAVEL: str = ""
    LLM_PROFILE_SOCIAL: str = ""

    # ----------------------------------------------------- Computed views

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def DATABASE_URL(self) -> str:
        """Bolt URL with embedded credentials, for `neomodel.config.DATABASE_URL`."""
        return (
            f"bolt://{self.NEO4J_USER}:{self.NEO4J_PASSWORD}"
            f"@{self.NEO4J_HOST}:{self.NEO4J_PORT}"
        )

    # -------------------------------------------------- LLM role registry

    #: Canonical set of LLM roles known to the gateway. Adding a role here
    #: gives it an env-var override (`LLM_PROFILE_<UPPER>`); omitting it
    #: simply means the gateway will fall back to `LLM_PROFILE_DEFAULT`.
    LLM_ROLES: tuple[str, ...] = (
        "agent",
        "supervisor",
        "graphiti",
        "onboarding",
        "food",
        "profile",
        "travel",
        "social",
    )

    #: Providers the gateway knows how to instantiate. Keep in sync with
    #: `src/app/services/llm_gateway.py::LLMGateway._build`.
    LLM_KNOWN_PROVIDERS: frozenset[str] = frozenset(
        {"groq", "openai", "ollama", "openrouter", "gemini"}
    )

    def llm_profile_for(self, role: str) -> str:
        """Resolve a role to its `provider:model` profile string.

        Falls back to `LLM_PROFILE_DEFAULT` if the role-specific override
        is empty / unset. Unknown roles also fall back to default.
        """
        attr = f"LLM_PROFILE_{role.upper()}"
        spec = getattr(self, attr, "") or self.LLM_PROFILE_DEFAULT
        return spec

    # --------------------------------------------------------- Validators

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_csv_origins(cls, v: object) -> object:
        """Allow `CORS_ORIGINS` to be a comma-separated string in `.env`."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _compute_neo4j_uri(self) -> "Settings":
        if not self.NEO4J_URI:
            self.NEO4J_URI = f"bolt://{self.NEO4J_HOST}:{self.NEO4J_PORT}"
        return self

    @model_validator(mode="after")
    def _validate_mcp_provider(self) -> "Settings":
        """Catch MCP_PROVIDER misconfiguration at boot, not at first request."""
        provider = (self.MCP_PROVIDER or "").lower()
        known = {"mock", "foursquare"}
        if provider not in known:
            raise RuntimeError(
                f"MCP_PROVIDER={self.MCP_PROVIDER!r} is invalid; "
                f"choose one of {sorted(known)}"
            )
        if provider == "foursquare" and not self.FOURSQUARE_API_KEY:
            raise RuntimeError(
                "MCP_PROVIDER=foursquare but FOURSQUARE_API_KEY is empty. "
                "Get one at https://location.foursquare.com/developer/ and "
                "add it to .env."
            )
        return self

    @model_validator(mode="after")
    def _validate_llm_profiles(self) -> "Settings":
        """Catch typos like `grok:llama-3` (vs `groq:`) at boot, not at first
        request. Validates only the *format* — actual model availability is
        validated lazily by the gateway when a role is first requested.
        """
        problems: list[str] = []

        def _check(name: str, spec: str) -> None:
            if not spec:
                return
            if ":" not in spec:
                problems.append(
                    f"{name}={spec!r} must be of the form 'provider:model'"
                )
                return
            provider, _, model = spec.partition(":")
            if not provider or not model:
                problems.append(
                    f"{name}={spec!r} must be 'provider:model' with both halves"
                )
                return
            if provider not in self.LLM_KNOWN_PROVIDERS:
                problems.append(
                    f"{name}={spec!r}: unknown provider {provider!r}; "
                    f"known: {sorted(self.LLM_KNOWN_PROVIDERS)}"
                )

        _check("LLM_PROFILE_DEFAULT", self.LLM_PROFILE_DEFAULT)
        for role in self.LLM_ROLES:
            attr = f"LLM_PROFILE_{role.upper()}"
            _check(attr, getattr(self, attr, ""))

        if problems:
            joined = "\n  - ".join(problems)
            raise RuntimeError(
                "Refusing to boot with invalid LLM profile config:\n  - " + joined
            )
        return self

    @model_validator(mode="after")
    def _refuse_unsafe_production_defaults(self) -> "Settings":
        """Hard-stop boot if production is configured with public placeholders."""
        if not self.is_production:
            return self

        problems: list[str] = []

        if self.SECRET_KEY in {"", _PLACEHOLDER_SECRET_KEY}:
            problems.append(
                "SECRET_KEY is empty or the public placeholder. Generate one with: "
                "python -c 'import secrets; print(secrets.token_urlsafe(64))'"
            )
        if self.NEO4J_PASSWORD in _PLACEHOLDER_NEO4J_PASSWORDS:
            problems.append(
                f"NEO4J_PASSWORD is the well-known default {self.NEO4J_PASSWORD!r}."
            )
        if not self.GROQ_API_KEY:
            problems.append("GROQ_API_KEY is empty.")

        if problems:
            joined = "\n  - ".join(problems)
            raise RuntimeError(
                "Refusing to boot in production with insecure configuration:\n  - "
                + joined
            )
        return self


settings = Settings()
