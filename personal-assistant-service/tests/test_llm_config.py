"""Unit tests for canonical LLM configuration."""

from unittest.mock import MagicMock, patch

import pytest

from app.llm_config import get_model, validate_model_config
from app.settings import Settings


def _settings(**overrides) -> Settings:
    values = {
        "llm_provider": "deepseek",
        "llm_model": "deepseek-chat",
        "llm_credential_provider": "deepseek-identity-provider",
        "llm_timeout_seconds": 30,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_get_model_fetches_api_key_from_agent_identity():
    settings = _settings()
    with (
        patch(
            "app.llm_config._get_api_key_from_identity",
            return_value="identity-deepseek-key",
        ) as mock_get_key,
        patch("app.llm_config.init_chat_model") as mock_init,
    ):
        mock_model = MagicMock()
        mock_init.return_value = mock_model

        result = get_model(settings=settings)

        assert result is mock_model
        mock_get_key.assert_called_once_with("deepseek-identity-provider")
        mock_init.assert_called_once_with(
            model="openai:deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key="identity-deepseek-key",
            timeout=30.0,
        )


def test_canonical_base_url_override():
    settings = _settings(llm_base_url="https://custom.example.com/v1")
    with (
        patch(
            "app.llm_config._get_api_key_from_identity",
            return_value="identity-key",
        ),
        patch("app.llm_config.init_chat_model") as mock_init,
    ):
        get_model(settings=settings)

    assert mock_init.call_args.kwargs["base_url"] == "https://custom.example.com/v1"


def test_validate_model_config_does_not_fetch_api_key():
    with patch("app.llm_config._get_api_key_from_identity") as mock_get_key:
        validate_model_config(settings=_settings())

    mock_get_key.assert_not_called()


def test_unknown_provider_raises_with_available_list():
    with pytest.raises(ValueError, match="Available: deepseek"):
        validate_model_config(settings=_settings(llm_provider="unknown"))


def test_explicit_provider_must_match_canonical_setting():
    with pytest.raises(ValueError, match="must match LLM_PROVIDER"):
        validate_model_config(provider="other", settings=_settings())


def test_identity_provider_returns_empty_key_raises():
    with (
        patch("app.llm_config.require_api_key") as mock_decorator,
        pytest.raises(ValueError, match="empty API key"),
    ):
        mock_decorator.return_value = lambda fn: lambda *args, **kwargs: fn(api_key="")
        get_model(settings=_settings())


def test_legacy_model_env_vars_are_ignored(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "legacy-model")
    monkeypatch.setenv("MODEL_URL", "https://legacy.example.com")
    monkeypatch.setenv("MODEL_API_KEY", "legacy-secret")
    settings = _settings()

    with (
        patch(
            "app.llm_config._get_api_key_from_identity",
            return_value="identity-key",
        ),
        patch("app.llm_config.init_chat_model") as mock_init,
    ):
        get_model(settings=settings)

    assert mock_init.call_args.kwargs["model"] == "openai:deepseek-chat"
    assert mock_init.call_args.kwargs["base_url"] == "https://api.deepseek.com"
    assert mock_init.call_args.kwargs["api_key"] == "identity-key"
