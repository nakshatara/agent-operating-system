from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

PROVIDERS = ("anthropic", "openai", "simulated")
REAL_PROVIDERS = ("anthropic", "openai")
DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-5-5"

ANTHROPIC_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-2")
# Not exhaustive; extend via OPENAI_EXTRA_MODELS.
OPENAI_MODELS = ("gpt-4o", "gpt-4o-mini", "gpt-4.1")
SIMULATED_MODELS = ("simulated-echo",)


@dataclass(frozen=True)
class ModelInfo:
    provider: str
    id: str
    input_per_mtok: float | None = None  # USD per million tokens, from PRICING_JSON only
    output_per_mtok: float | None = None


def _pricing(provider: str, model: str) -> tuple[float | None, float | None]:
    entry = settings.pricing().get(f"{provider}:{model}")
    if not isinstance(entry, dict):
        return None, None

    def num(v: object) -> float | None:
        return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None

    return num(entry.get("input_per_mtok")), num(entry.get("output_per_mtok"))


def list_models() -> list[ModelInfo]:
    ids: list[tuple[str, str]] = [("anthropic", m) for m in ANTHROPIC_MODELS]
    ids += [("openai", m) for m in (*OPENAI_MODELS, *settings.openai_extra_model_list)]
    ids += [("simulated", m) for m in SIMULATED_MODELS]
    out: list[ModelInfo] = []
    seen: set[tuple[str, str]] = set()
    for provider, model in ids:
        if (provider, model) in seen:
            continue
        seen.add((provider, model))
        i, o = _pricing(provider, model)
        out.append(ModelInfo(provider, model, i, o))
    return out


def find_model(provider: str, model: str) -> ModelInfo | None:
    for info in list_models():
        if info.provider == provider and info.id == model:
            return info
    return None


def provider_configured(provider: str) -> bool:
    """True if the provider can serve live traffic (API key present). 'simulated' is never 'live'."""
    return bool(settings.provider_api_key(provider))


def estimate_cost(
    provider: str, model: str, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    """Cost estimate in USD, or None if pricing or token counts are unavailable."""
    info = find_model(provider, model)
    if info is None or input_tokens is None or output_tokens is None:
        return None
    if info.input_per_mtok is None or info.output_per_mtok is None:
        return None
    return (input_tokens * info.input_per_mtok + output_tokens * info.output_per_mtok) / 1_000_000
