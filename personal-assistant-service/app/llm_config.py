"""LLM Provider resolution and AgentArts Identity credential loading."""

from dataclasses import dataclass

from agentarts.sdk import require_api_key
from langchain.chat_models import BaseChatModel, init_chat_model

from app.provider_catalog import get_provider_metadata
from app.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class ResolvedModelConfig:
    provider: str
    model: str
    base_url: str
    credential_provider: str
    timeout_seconds: float


def _resolve_provider(
    provider: str | None = None,
    settings: Settings | None = None,
) -> ResolvedModelConfig:
    """Resolve canonical Settings against the internal Provider catalog."""
    current = settings or get_settings()
    provider_name = (provider or current.llm_provider).lower()

    if provider is not None and provider_name != current.llm_provider:
        raise ValueError(
            "Explicit provider selection must match LLM_PROVIDER. "
            "Configure the desired Provider through the canonical setting."
        )

    metadata = get_provider_metadata(provider_name)
    base_url = (
        str(current.llm_base_url).rstrip("/")
        if current.llm_base_url
        else str(metadata.base_url).rstrip("/")
    )
    return ResolvedModelConfig(
        provider=provider_name,
        model=current.llm_model,
        base_url=base_url,
        credential_provider=current.llm_credential_provider,
        timeout_seconds=current.llm_timeout_seconds,
    )


def validate_model_config(
    provider: str | None = None,
    settings: Settings | None = None,
) -> None:
    """Validate model metadata without fetching a Secret."""
    _resolve_provider(provider, settings)


def _get_api_key_from_identity(credential_provider_name: str) -> str:
    """Fetch an API key exclusively through AgentArts Identity."""

    @require_api_key(provider_name=credential_provider_name, into="api_key")
    def _fetch(api_key: str | None = None) -> str:
        if not api_key:
            raise ValueError(
                f"AgentArts Identity provider '{credential_provider_name}' "
                "returned an empty API key."
            )
        return api_key

    return _fetch()


def get_model(
    provider: str | None = None,
    settings: Settings | None = None,
) -> BaseChatModel:
    """Build an OpenAI-compatible model from Settings and Identity."""
    config = _resolve_provider(provider, settings)
    api_key = _get_api_key_from_identity(config.credential_provider)
    return init_chat_model(
        model=f"openai:{config.model}",
        base_url=config.base_url,
        api_key=api_key,
        timeout=config.timeout_seconds,
    )
