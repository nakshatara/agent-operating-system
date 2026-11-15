from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class ProviderError(Exception):
    """Clean, user-presentable provider failure. Never contains API keys."""

    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class ProviderNotConfigured(ProviderError):
    pass


@dataclass(frozen=True)
class ModelRequest:
    model: str
    prompt: str
    system: str | None = None
    max_tokens: int = 1024
    temperature: float | None = None


@dataclass(frozen=True)
class ModelResponse:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    model: str
    latency_ms: int
    provider: str
    simulated: bool = False


@runtime_checkable
class ModelProvider(Protocol):
    name: str

    async def complete(self, request: ModelRequest) -> ModelResponse: ...
