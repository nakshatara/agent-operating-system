from __future__ import annotations

from app.core.config import settings
from app.modules.model_gateway.anthropic import AnthropicProvider
from app.modules.model_gateway.base import ModelProvider, ProviderError, ProviderNotConfigured
from app.modules.model_gateway.openai import OpenAIProvider
from app.modules.model_gateway.simulated import SimulatedProvider


def get_provider(provider: str, mode: str) -> ModelProvider:
    """Select an adapter. Mode 'simulated' ALWAYS yields the SimulatedProvider; 'live' never does."""
    if mode == "simulated":
        return SimulatedProvider()
    if mode != "live":
        raise ProviderError(f"unknown execution mode '{mode}'")
    key = settings.provider_api_key(provider)
    if provider not in ("anthropic", "openai"):
        raise ProviderError(f"provider '{provider}' cannot be used in live mode")
    if not key:
        raise ProviderNotConfigured(f"No API key configured for provider '{provider}'")
    kwargs = dict(
        max_retries=settings.provider_max_retries,
        backoff_seconds=settings.provider_backoff_seconds,
        timeout=settings.provider_timeout_seconds,
    )
    if provider == "anthropic":
        return AnthropicProvider(key, **kwargs)
    return OpenAIProvider(key, **kwargs)
