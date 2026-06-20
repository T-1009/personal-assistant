"""Typed runtime configuration.

`.env.example` is the user-facing configuration catalog. This module is the
only production-code entry point for application environment variables.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Immutable application settings loaded from env or the local `.env`."""

    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-v4-pro"
    llm_base_url: AnyHttpUrl | None = None
    llm_credential_provider: str = "DEEPSEEK_API_KEY"
    llm_timeout_seconds: float = Field(default=60.0, gt=0.0)
    llm_agent_bundle_ttl_seconds: float = Field(default=300.0, gt=0.0)

    postgres_dsn: str | None = None
    sqlite_db_path: Path | None = None

    gitee_provider_name: str = "gitee-provider"
    iam_users_provider_name: str = "iam-users-readonly"
    iam_users_agency_session_name: str = "personal-assistant-iam-users-readonly"
    iam_users_region: str = "cn-southwest-2"
    iam_users_endpoint: AnyHttpUrl | None = None

    @field_validator(
        "llm_base_url",
        "postgres_dsn",
        "sqlite_db_path",
        "iam_users_endpoint",
        mode="before",
    )
    @classmethod
    def empty_string_is_none(cls, value):
        """Treat empty optional env values as unset."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "llm_provider",
        "llm_model",
        "llm_credential_provider",
        "gitee_provider_name",
        "iam_users_provider_name",
        "iam_users_agency_session_name",
        "iam_users_region",
        mode="before",
    )
    @classmethod
    def require_non_empty_string(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    @field_validator("llm_provider")
    @classmethod
    def normalize_provider_name(cls, value: str) -> str:
        return value.lower()

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value):
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_persistence_backend(self):
        if self.postgres_dsn and self.sqlite_db_path:
            raise ValueError("POSTGRES_DSN and SQLITE_DB_PATH are mutually exclusive")
        return self

    @property
    def effective_iam_users_endpoint(self) -> str:
        if self.iam_users_endpoint:
            return str(self.iam_users_endpoint).rstrip("/")
        return f"https://iam.{self.iam_users_region}.myhuaweicloud.com"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable Settings instance."""
    return Settings()
