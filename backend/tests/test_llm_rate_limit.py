"""A brief provider rate limit (HTTP 429) is retried; a persistent one gives a clear, non-key-related message."""
import asyncio

import httpx
import pytest

from app.config import Settings
from app.core.exceptions import KothaError
from app.services import llm_provider as lp


def settings() -> Settings:
    return Settings(_env_file=None, llm_provider="openai_compatible", llm_model="m", llm_api_key="k", llm_base_url="https://x.test/v1")


def install(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(lp.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    waits = []

    async def fake_sleep(s):
        waits.append(s)

    monkeypatch.setattr(lp.asyncio, "sleep", fake_sleep)
    return waits


def ok():
    return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})


def test_retries_429_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(429, headers={"retry-after": "1"}) if calls["n"] < 3 else ok()

    waits = install(monkeypatch, handler)
    assert asyncio.run(lp.OpenAICompatProvider(settings()).complete("s", "u")) == "{}"
    assert calls["n"] == 3 and waits == [1.0, 1.0]


def test_persistent_429_is_a_clear_rate_limit_error(monkeypatch):
    install(monkeypatch, lambda request: httpx.Response(429))
    with pytest.raises(KothaError) as e:
        asyncio.run(lp.OpenAICompatProvider(settings()).complete("s", "u"))
    assert e.value.code == "PROVIDER_RATE_LIMITED" and e.value.status_code == 503
    assert "API key" not in e.value.message


def test_retry_wait_is_capped():
    assert lp.retry_wait_seconds(httpx.Response(429, headers={"retry-after": "999"}), 0) == lp.MAX_RETRY_WAIT_SECONDS


def test_other_errors_are_not_retried(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401)

    install(monkeypatch, handler)
    with pytest.raises(KothaError) as e:
        asyncio.run(lp.OpenAICompatProvider(settings()).complete("s", "u"))
    assert e.value.code == "PROVIDER_ERROR" and calls["n"] == 1
