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
    GRAPHITI_HOST: str = "localhost"
    GRAPHITI_PORT: int = 8080
    GRAPHITI_URL: str = "http://localhost:8080"

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
