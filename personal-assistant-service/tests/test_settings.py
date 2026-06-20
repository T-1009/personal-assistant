"""Tests for the single Runtime Settings entry point."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults():
    settings = Settings(_env_file=None)

    assert settings.log_level == "INFO"
    assert settings.llm_provider == "deepseek"
    assert settings.llm_model == "deepseek-v4-pro"
    assert settings.llm_agent_bundle_ttl_seconds == 300.0
    assert settings.postgres_dsn is None
    assert settings.sqlite_db_path is None


def test_environment_overrides_defaults(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("LLM_MODEL", "deepseek-reasoner")

    settings = Settings(_env_file=None)

    assert settings.log_level == "DEBUG"
    assert settings.llm_model == "deepseek-reasoner"


def test_dotenv_is_supported_without_mutating_os_environ(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=dotenv-model\n", encoding="utf-8")
    monkeypatch.delenv("LLM_MODEL", raising=False)

    settings = Settings(_env_file=env_file)

    assert settings.llm_model == "dotenv-model"
    assert "LLM_MODEL" not in __import__("os").environ


def test_environment_takes_priority_over_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=dotenv-model\n", encoding="utf-8")
    monkeypatch.setenv("LLM_MODEL", "runtime-model")

    settings = Settings(_env_file=env_file)

    assert settings.llm_model == "runtime-model"


def test_persistence_backends_are_mutually_exclusive():
    with pytest.raises(ValidationError, match="mutually exclusive"):
        Settings(
            _env_file=None,
            postgres_dsn="postgresql://localhost/test",
            sqlite_db_path=Path("/tmp/checkpoints.db"),
        )


def test_invalid_log_level_fails_fast():
    with pytest.raises(ValidationError, match="log_level"):
        Settings(_env_file=None, log_level="TRACE")


def test_agent_bundle_ttl_can_be_overridden(monkeypatch):
    monkeypatch.setenv("LLM_AGENT_BUNDLE_TTL_SECONDS", "120")

    settings = Settings(_env_file=None)

    assert settings.llm_agent_bundle_ttl_seconds == 120.0


@pytest.mark.parametrize("ttl", [0, -1])
def test_agent_bundle_ttl_must_be_positive(ttl):
    with pytest.raises(ValidationError, match="llm_agent_bundle_ttl_seconds"):
        Settings(_env_file=None, llm_agent_bundle_ttl_seconds=ttl)


def test_empty_optional_values_are_unset():
    settings = Settings(
        _env_file=None,
        llm_base_url="",
        postgres_dsn="",
        sqlite_db_path="",
        iam_users_endpoint="",
    )

    assert settings.llm_base_url is None
    assert settings.postgres_dsn is None
    assert settings.sqlite_db_path is None
    assert settings.iam_users_endpoint is None


def test_settings_are_frozen():
    settings = Settings(_env_file=None)

    with pytest.raises(ValidationError):
        settings.llm_model = "changed"
