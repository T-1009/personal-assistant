"""Internal, typed LLM Provider metadata.

This is release metadata reviewed with code, not a user configuration entry.
"""

from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict


class ProviderMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: Literal["openai-compatible"]
    base_url: AnyHttpUrl
    capabilities: frozenset[str]


PROVIDER_CATALOG: dict[str, ProviderMetadata] = {
    "deepseek": ProviderMetadata(
        protocol="openai-compatible",
        base_url="https://api.deepseek.com",
        capabilities=frozenset({"streaming", "tools", "reasoning"}),
    ),
}


def get_provider_metadata(provider_name: str) -> ProviderMetadata:
    """Resolve an internal Provider entry or raise an actionable error."""
    try:
        return PROVIDER_CATALOG[provider_name]
    except KeyError as exc:
        available = ", ".join(sorted(PROVIDER_CATALOG))
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider_name}'. Available: {available}"
        ) from exc
