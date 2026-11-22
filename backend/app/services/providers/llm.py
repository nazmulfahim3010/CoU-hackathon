"""Provider-independent LLM client. Returns raw text; callers validate it."""
from __future__ import annotations

from typing import Protocol

import httpx

from app.config import Settings
from app.core.exceptions import KothaError
from app.core.logging import get_logger

log = get_logger("llm")


class LLMClient(Protocol):
    name: str

    async def complete(self, system: str, user: str, max_tokens: int = 1500) -> str: ...


def raise_for_provider(exc: Exception, provider: str) -> None:
    """Translate transport errors into KothaError without leaking response bodies."""
    if isinstance(exc, httpx.TimeoutException):
        raise KothaError(504, "PROVIDER_TIMEOUT", f"{provider} timed out.") from exc
    if isinstance(exc, httpx.HTTPStatusError):
        log.warning("provider=%s status=%s", provider, exc.response.status_code)
        raise KothaError(502, "PROVIDER_ERROR", f"{provider} returned HTTP {exc.response.status_code}.") from exc
    raise KothaError(502, "PROVIDER_UNREACHABLE", f"Could not reach or parse response from {provider}.") from exc


class AnthropicClient:
    """Anthropic Messages API (POST /v1/messages)."""

    name = "anthropic"

    def __init__(self, s: Settings):
        self._key, self._model = s.llm_api_key, s.llm_model
        self._base = (s.llm_base_url or "https://api.anthropic.com").rstrip("/")
        self._timeout = s.provider_timeout_seconds

    async def complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{self._base}/v1/messages",
                    headers={"x-api-key": self._key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": self._model, "max_tokens": max_tokens, "temperature": 0, "system": system,
                          "messages": [{"role": "user", "content": user}]},
                )
                r.raise_for_status()
                blocks = r.json().get("content", [])
                return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        except (httpx.HTTPError, ValueError) as exc:
            raise_for_provider(exc, "anthropic")
            raise


class OpenAICompatClient:
    """Any OpenAI-compatible /chat/completions endpoint."""

    name = "openai_compatible"

    def __init__(self, s: Settings):
        self._key, self._model = s.llm_api_key, s.llm_model
        self._base = (s.llm_base_url or "https://api.openai.com/v1").rstrip("/")
        self._timeout = s.provider_timeout_seconds

    async def complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{self._base}/chat/completions",
                    headers={"Authorization": f"Bearer {self._key}"},
                    json={"model": self._model, "temperature": 0, "max_tokens": max_tokens,
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise_for_provider(exc, "openai_compatible")
            raise


def llm_configured(s: Settings) -> bool:
    return s.llm_provider in ("anthropic", "openai_compatible") and bool(s.llm_api_key and s.llm_model)


def get_llm(s: Settings) -> LLMClient:
    if not llm_configured(s):
        raise KothaError(503, "PROVIDER_NOT_CONFIGURED",
                         "No LLM provider is configured (set LLM_PROVIDER, LLM_MODEL, LLM_API_KEY), or use demo mode.")
    return AnthropicClient(s) if s.llm_provider == "anthropic" else OpenAICompatClient(s)
