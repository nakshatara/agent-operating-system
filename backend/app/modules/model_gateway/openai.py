from __future__ import annotations

import asyncio
import time

import httpx

from app.modules.model_gateway.base import ModelRequest, ModelResponse, ProviderError
from app.modules.model_gateway.http import Sleep, post_json_with_retry

OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        url: str = OPENAI_URL,
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
        messages: list[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        body: dict = {
            "model": request.model,
            "messages": messages,
            "max_completion_tokens": request.max_tokens,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }
        start = time.perf_counter()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            data = await post_json_with_retry(
                client,
                self._url,
                provider="openai",
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

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("openai response missing choices")
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        usage = data.get("usage") or {}
        return ModelResponse(
            text=text,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            model=str(data.get("model") or request.model),
            latency_ms=latency_ms,
            provider="openai",
        )
