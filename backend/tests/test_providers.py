import json

import httpx
import pytest

from app.modules.agents.readiness import compute_readiness
from app.modules.model_gateway.anthropic import AnthropicProvider
from app.modules.model_gateway.base import ModelRequest, ProviderError
from app.modules.model_gateway.gateway import get_provider
from app.modules.model_gateway.openai import OpenAIProvider
from app.modules.model_gateway.simulated import SIMULATED_PREFIX, SimulatedProvider

REQ = ModelRequest(model="claude-sonnet-5-5", prompt="hello", system="be brief")


async def no_sleep(_):
    return None


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_simulated_is_labelled_and_has_no_tokens():
    resp = await SimulatedProvider().complete(REQ)
    assert resp.text.startswith(SIMULATED_PREFIX)
    assert "hello" in resp.text
    assert resp.simulated and resp.input_tokens is None and resp.output_tokens is None


def test_mode_simulated_never_uses_real_provider():
    assert isinstance(get_provider("anthropic", "simulated"), SimulatedProvider)


def test_live_without_key_is_rejected(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", None)
    with pytest.raises(ProviderError):
        get_provider("anthropic", "live")
    assert compute_readiness("live", "anthropic") == "configured"
    assert compute_readiness("simulated", "anthropic") == "simulated"
    monkeypatch.setattr(settings, "anthropic_api_key", "k")
    assert compute_readiness("live", "anthropic") == "live"


async def test_anthropic_request_and_parse():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-sonnet-5-5",
                "content": [{"type": "text", "text": "hi "}, {"type": "text", "text": "there"}],
                "usage": {"input_tokens": 11, "output_tokens": 3},
            },
        )

    async with _client(handler) as c:
        resp = await AnthropicProvider("sk-test", client=c, sleep=no_sleep).complete(REQ)
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "sk-test"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["body"]["system"] == "be brief"
    assert seen["body"]["messages"] == [{"role": "user", "content": "hello"}]
    assert resp.text == "hi there"
    assert (resp.input_tokens, resp.output_tokens) == (11, 3)
    assert not resp.simulated


async def test_openai_request_and_parse():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "gpt-4o",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
        )

    async with _client(handler) as c:
        resp = await OpenAIProvider("sk-o", client=c, sleep=no_sleep).complete(
            ModelRequest(model="gpt-4o", prompt="p", system="s")
        )
    assert seen["auth"] == "Bearer sk-o"
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]
    assert resp.text == "ok" and resp.input_tokens == 5 and resp.output_tokens == 2


async def test_retry_on_429_then_success():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": {"message": "slow down"}})
        return httpx.Response(200, json={"content": [{"type": "text", "text": "done"}], "usage": {}})

    async with _client(handler) as c:
        resp = await AnthropicProvider("k", client=c, sleep=no_sleep).complete(REQ)
    assert calls["n"] == 3 and resp.text == "done"


async def test_5xx_exhausts_retries_with_clean_error():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503, json={"error": {"message": "overloaded"}})

    async with _client(handler) as c:
        with pytest.raises(ProviderError) as e:
            await AnthropicProvider("secret-key", client=c, max_retries=2, sleep=no_sleep).complete(REQ)
    assert calls["n"] == 3
    assert "503" in e.value.message and "secret-key" not in e.value.message


async def test_4xx_not_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(400, json={"error": {"message": "bad model"}})

    async with _client(handler) as c:
        with pytest.raises(ProviderError) as e:
            await OpenAIProvider("k", client=c, sleep=no_sleep).complete(REQ)
    assert calls["n"] == 1 and "bad model" in e.value.message


async def test_timeout_is_retried_then_surfaced():
    def handler(request):
        raise httpx.ReadTimeout("t", request=request)

    async with _client(handler) as c:
        with pytest.raises(ProviderError) as e:
            await AnthropicProvider("k", client=c, max_retries=1, sleep=no_sleep).complete(REQ)
    assert "timed out" in e.value.message
