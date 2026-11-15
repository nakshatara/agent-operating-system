from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.modules.model_gateway.base import ProviderError

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504, 529}
Sleep = Callable[[float], Awaitable[None]]


def _error_message(provider: str, resp: httpx.Response) -> str:
    detail = ""
    try:
        body = resp.json()
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            detail = str(err.get("message", ""))
        elif isinstance(err, str):
            detail = err
    except ValueError:
        pass
    detail = detail[:300]
    return f"{provider} request failed with HTTP {resp.status_code}" + (f": {detail}" if detail else "")


async def post_json_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    provider: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
    max_retries: int,
    backoff_seconds: float,
    timeout: float,
    sleep: Sleep = asyncio.sleep,
) -> dict[str, Any]:
    """POST JSON with bounded retries on timeouts, transport errors, 429 and 5xx."""
    last_error: ProviderError | None = None
    for attempt in range(max_retries + 1):
        retry_after: float | None = None
        try:
            resp = await client.post(url, headers=headers, json=json_body, timeout=timeout)
        except httpx.TimeoutException:
            last_error = ProviderError(f"{provider} request timed out", retryable=True)
        except httpx.TransportError as exc:
            last_error = ProviderError(
                f"{provider} network error: {type(exc).__name__}", retryable=True
            )
        else:
            if resp.status_code < 400:
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise ProviderError(f"{provider} returned a non-JSON response") from exc
                if not isinstance(data, dict):
                    raise ProviderError(f"{provider} returned an unexpected response shape")
                return data
            last_error = ProviderError(
                _error_message(provider, resp),
                status_code=resp.status_code,
                retryable=resp.status_code in RETRYABLE_STATUS,
            )
            if not last_error.retryable:
                raise last_error
            header = resp.headers.get("retry-after")
            if header:
                try:
                    retry_after = min(float(header), 30.0)
                except ValueError:
                    retry_after = None
        if attempt < max_retries:
            delay = retry_after if retry_after is not None else backoff_seconds * (2**attempt)
            logger.warning("%s call failed (%s); retry %d in %.1fs", provider, last_error, attempt + 1, delay)
            await sleep(delay)
    assert last_error is not None
    raise last_error
