from __future__ import annotations

import asyncio
import time

import httpx

from app.modules.model_gateway.base import ModelRequest, ModelResponse, ProviderError
from app.modules.model_gateway.http import Sleep, post_json_with_retry

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        url: str = ANTHROPIC_URL,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        timeout: float = 60.0,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._api_key = api_key
        self._client = client
        self._url = url
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._timeout = timeout
        self._sleep = sleep

    async def complete(self, request: ModelRequest) -> ModelResponse:
        body: dict = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system:
            body["system"] = request.system
        if request.temperature is not None:
            body["temperature"] = request.temperature
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        start = time.perf_counter()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            data = await post_json_with_retry(
                client,
                self._url,
                provider="anthropic",
                headers=headers,
                json_body=body,
                max_retries=self._max_retries,
                backoff_seconds=self._backoff,
                timeout=self._timeout,
                sleep=self._sleep,
            )
        finally:
            if owns_client:
                await client.aclose()
        latency_ms = int((time.perf_counter() - start) * 1000)

        blocks = data.get("content")
        if not isinstance(blocks, list):
            raise ProviderError("anthropic response missing content")
        text = "".join(
            b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
        )
        usage = data.get("usage") or {}
        return ModelResponse(
            text=text,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            model=str(data.get("model") or request.model),
            latency_ms=latency_ms,
            provider="anthropic",
        )
