"""Cerebras-first chat client. Router and generation use separate models and fallbacks."""

from __future__ import annotations

import json
import re
import threading
import time
from contextvars import ContextVar
from typing import Any

import httpx

from app.config import get_settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
GROQ_GEN_MODEL = "openai/gpt-oss-120b"
GROQ_ROUTER_MODEL = "openai/gpt-oss-20b"
GEN_MAX_TOKENS = 2000
ROUTER_MAX_TOKENS = 400
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)

_calls: ContextVar[list[dict] | None] = ContextVar("llm_calls", default=None)


class LLMError(RuntimeError):
    pass


class TokenBucket:
    """Five gpt-oss-120b requests per minute. Empty means skip, not wait."""

    def __init__(self, rate: int = 5, per_seconds: float = 60.0) -> None:
        self.rate = rate
        self.per_seconds = per_seconds
        self.tokens = float(rate)
        self.updated = time.monotonic()
        self._lock = threading.Lock()

    def take(self) -> bool:
        with self._lock:
            now = time.monotonic()
            refill = (now - self.updated) * (self.rate / self.per_seconds)
            self.tokens = min(float(self.rate), self.tokens + refill)
            self.updated = now
            if self.tokens < 1:
                return False
            self.tokens -= 1
            return True


GEN_BUCKET = TokenBucket()
_HTTP: httpx.Client | None = None


def get_http() -> httpx.Client:
    global _HTTP
    if _HTTP is None:
        _HTTP = httpx.Client(
            timeout=httpx.Timeout(25.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=8, max_connections=16, keepalive_expiry=120.0),
        )
    return _HTTP


def warm_http() -> None:
    settings = get_settings()
    client = get_http()
    headers = {"Authorization": f"Bearer {settings.cerebras_api_key}"} if settings.cerebras_api_key else {}
    try:
        client.get("https://api.cerebras.ai/v1/models", headers=headers)
    except httpx.HTTPError:
        return


def start_llm_log() -> None:
    _calls.set([])


def llm_calls() -> list[dict]:
    current = _calls.get()
    if current is None:
        current = []
        _calls.set(current)
    return current


def _record(entry: dict) -> None:
    llm_calls().append(entry)


def _message_content(body: dict) -> str:
    return body["choices"][0]["message"]["content"]


def _usage(body: dict) -> tuple[int, int]:
    usage = body.get("usage") or {}
    return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def _post(
    url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    *,
    reasoning_effort: str | None,
    max_tokens: int,
    timeout: float,
) -> tuple[str, int, int]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    response = get_http().post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=timeout,
    )
    if response.status_code >= 400:
        detail = response.text[:300].replace("\n", " ")
        raise httpx.HTTPStatusError(
            f"HTTP {response.status_code}: {detail}",
            request=response.request,
            response=response,
        )
    body = response.json()
    tokens_in, tokens_out = _usage(body)
    return _message_content(body), tokens_in, tokens_out


def _attempt(
    *,
    stage: str,
    provider: str,
    url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    reasoning_effort: str | None,
    max_tokens: int,
    timeout: float,
) -> str | None:
    started = time.perf_counter()
    try:
        content, tokens_in, tokens_out = _post(
            url,
            api_key,
            model,
            messages,
            reasoning_effort=reasoning_effort,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        _record(
            {
                "stage": stage,
                "provider": provider,
                "model": model,
                "tokens_in": 0,
                "tokens_out": 0,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": f"{type(exc).__name__}: {exc}"[:300],
            }
        )
        return None
    _record(
        {
            "stage": stage,
            "provider": provider,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error": "",
        }
    )
    return content


def _parse_json(raw: str) -> dict:
    text = _THINK.sub("", raw).strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    return json.loads(text)


def complete_router_json(system: str, user: str) -> dict:
    """One combined router and rewrite call. Qwen with reasoning off, then Groq 20b."""
    settings = get_settings()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if settings.cerebras_api_key and settings.router_model:
        raw = _attempt(
            stage="router",
            provider="cerebras",
            url=CEREBRAS_URL,
            api_key=settings.cerebras_api_key,
            model=settings.router_model,
            messages=messages,
            reasoning_effort="none",
            max_tokens=ROUTER_MAX_TOKENS,
            timeout=15,
        )
        if raw is not None:
            try:
                return _parse_json(raw)
            except json.JSONDecodeError as exc:
                _record(
                    {
                        "stage": "router",
                        "provider": "cerebras",
                        "model": settings.router_model,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "latency_ms": 0,
                        "error": f"JSONDecodeError: {exc}"[:300],
                    }
                )
    if settings.groq_api_key:
        raw = _attempt(
            stage="router",
            provider="groq",
            url=GROQ_URL,
            api_key=settings.groq_api_key,
            model=GROQ_ROUTER_MODEL,
            messages=messages,
            reasoning_effort="low",
            max_tokens=ROUTER_MAX_TOKENS,
            timeout=15,
        )
        if raw is not None:
            return _parse_json(raw)
    raise LLMError("router providers failed")


def complete_generate_json(system: str, user: str) -> dict:
    """gpt-oss-120b, then Qwen, then Groq. Skip gpt-oss when its per-minute bucket is empty."""
    settings = get_settings()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if settings.cerebras_api_key and settings.gen_model and GEN_BUCKET.take():
        raw = _attempt(
            stage="generate",
            provider="cerebras",
            url=CEREBRAS_URL,
            api_key=settings.cerebras_api_key,
            model=settings.gen_model,
            messages=messages,
            reasoning_effort="medium",
            max_tokens=GEN_MAX_TOKENS,
            timeout=25,
        )
        if raw is not None:
            return _parse_json(raw)
    if settings.cerebras_api_key and settings.gen_fallback_model:
        raw = _attempt(
            stage="generate",
            provider="cerebras",
            url=CEREBRAS_URL,
            api_key=settings.cerebras_api_key,
            model=settings.gen_fallback_model,
            messages=messages,
            reasoning_effort="none",
            max_tokens=GEN_MAX_TOKENS,
            timeout=20,
        )
        if raw is not None:
            return _parse_json(raw)
    if settings.groq_api_key:
        raw = _attempt(
            stage="generate",
            provider="groq",
            url=GROQ_URL,
            api_key=settings.groq_api_key,
            model=settings.groq_model or GROQ_GEN_MODEL,
            messages=messages,
            reasoning_effort="medium",
            max_tokens=GEN_MAX_TOKENS,
            timeout=25,
        )
        if raw is not None:
            return _parse_json(raw)
    raise LLMError("generation providers failed")
