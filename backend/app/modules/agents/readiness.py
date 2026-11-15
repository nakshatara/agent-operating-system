from __future__ import annotations

from app.modules.model_gateway.registry import provider_configured


def compute_readiness(execution_mode: str, provider: str) -> str:
    """simulated: runs through the SimulatedProvider (no model call).
    configured: set to live but the provider has no API key, so it cannot run live.
    live: set to live and the provider key is present."""
    if execution_mode == "simulated":
        return "simulated"
    return "live" if provider_configured(provider) else "configured"
