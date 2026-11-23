"""Provider-independent LLM client interface and adapters.

Candidate Verification:
- Anthropic: Messages API (POST /v1/messages). Model ID: claude-3-5-sonnet-20241022.
  Structured output via strict system JSON prompt instructions and zero temperature.
- OpenAI-Compatible: Chat completions (POST /chat/completions). Model ID: gpt-4o-mini or llama-3.3-70b-versatile.
  Supports response_format={"type": "json_object"}.
"""
from __future__ import annotations

from typing import Protocol
import httpx

from app.config import Settings
from app.core.exceptions import KothaError
from app.core.logging import get_logger

log = get_logger("llm_provider")


class LLMProvider(Protocol):
    name: str

    async def complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        ...


# Type alias for backward compatibility
LLMClient = LLMProvider


def raise_for_provider(exc: Exception, provider: str) -> None:
    """Translate transport errors into KothaError without leaking keys or raw data."""
    if isinstance(exc, httpx.TimeoutException):
        raise KothaError(
            504,
            "PROVIDER_TIMEOUT",
            f"{provider} সময়মতো সাড়া দেয়নি (Provider timed out). অনুগ্রহ করে আবার চেষ্টা করুন বা ডেমো মোড ব্যবহার করুন।",
        ) from exc
    if isinstance(exc, httpx.HTTPStatusError):
        log.warning("provider=%s status=%s", provider, exc.response.status_code)
        raise KothaError(
            502,
            "PROVIDER_ERROR",
            f"{provider} সেবায় ত্রুটি ঘটেছে (HTTP {exc.response.status_code}). অনুগ্রহ করে API key/মডেল সেটিংস পরীক্ষা করুন অথবা ডেমো মোড ব্যবহার করুন।",
        ) from exc
    raise KothaError(
        502,
        "PROVIDER_UNREACHABLE",
        f"{provider} সেবার সাথে যোগাযোগ করা যাচ্ছে না ({provider} unreachable). অনুগ্রহ করে ইন্টারনেট সংযোগ ও সেটিংস পরীক্ষা করুন অথবা ডেমো মোড ব্যবহার করুন।",
    ) from exc


class AnthropicProvider:
    """Anthropic Messages API (POST /v1/messages)."""

    name = "anthropic"

    def __init__(self, s: Settings):
        self._key = s.llm_api_key
        self._model = s.llm_model or "claude-3-5-sonnet-20241022"
        self._base = (s.llm_base_url or "https://api.anthropic.com").rstrip("/")
        self._timeout = s.provider_timeout_seconds

    async def complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{self._base}/v1/messages",
                    headers={
                        "x-api-key": self._key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "max_tokens": max_tokens,
                        "temperature": 0,
                        "system": system,
                        "messages": [{"role": "user", "content": user}],
                    },
                )
                r.raise_for_status()
                blocks = r.json().get("content", [])
                return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        except (httpx.HTTPError, ValueError) as exc:
            raise_for_provider(exc, "anthropic")
            raise


class OpenAICompatProvider:
    """Any OpenAI-compatible /chat/completions endpoint (OpenAI, Groq, vLLM)."""

    name = "openai_compatible"

    def __init__(self, s: Settings):
        self._key = s.llm_api_key
        self._model = s.llm_model or "gpt-4o-mini"
        self._base = (s.llm_base_url or "https://api.openai.com/v1").rstrip("/")
        self._timeout = s.provider_timeout_seconds

    async def complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                payload = {
                    "model": self._model,
                    "temperature": 0,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                }
                # Request JSON mode when prompt explicitly asks for JSON
                if "json" in system.lower():
                    payload["response_format"] = {"type": "json_object"}

                r = await c.post(
                    f"{self._base}/chat/completions",
                    headers={"Authorization": f"Bearer {self._key}"},
                    json=payload,
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise_for_provider(exc, "openai_compatible")
            raise


# Aliases for backwards compatibility
AnthropicClient = AnthropicProvider
OpenAICompatClient = OpenAICompatProvider


def llm_configured(s: Settings) -> bool:
    return s.llm_provider in ("anthropic", "openai_compatible") and bool(s.llm_api_key and s.llm_model)


def get_llm(s: Settings) -> LLMProvider:
    if not llm_configured(s):
        raise KothaError(
            503,
            "LLM_UNAVAILABLE",
            "ক্লিনিক্যাল তথ্য প্রক্রিয়াকরণের জন্য কোনো ভাষা মডেল (LLM) কনফিগার করা নেই (No LLM provider configured). অনুগ্রহ করে .env ফাইলে LLM_PROVIDER ও API key সেট করুন অথবা ডেমো মোড (Demo Mode) ব্যবহার করুন।",
        )
    return AnthropicProvider(s) if s.llm_provider == "anthropic" else OpenAICompatProvider(s)
