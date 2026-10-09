"""Groq chat client with one retry and a Cerebras fallback. JSON mode, 10s timeout."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import get_settings

TIMEOUT = 10.0
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"


class LLMError(RuntimeError):
    pass


def _post(
    url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    *,
    json_mode: bool,
    reasoning_effort: str | None,
    max_tokens: int | None,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    if max_tokens:
        payload["max_tokens"] = max_tokens
    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=TIMEOUT,
    )
    if response.status_code >= 400:
        detail = response.text[:300].replace("\n", " ")
        raise httpx.HTTPStatusError(
            f"HTTP {response.status_code}: {detail}",
            request=response.request,
            response=response,
        )
    return response.json()["choices"][0]["message"]["content"]


def _try_provider(
    url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    *,
    json_mode: bool,
    reasoning_effort: str | None,
    max_tokens: int | None,
) -> str:
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            return _post(
                url,
                api_key,
                model,
                messages,
                json_mode=json_mode,
                reasoning_effort=reasoning_effort,
                max_tokens=max_tokens,
            )
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def complete(
    messages: list[dict],
    *,
    json_mode: bool = False,
    reasoning_effort: str | None = None,
    max_tokens: int | None = None,
) -> str:
    settings = get_settings()
    errors: list[str] = []
    if settings.groq_api_key and settings.groq_model:
        try:
            return _try_provider(
                GROQ_URL,
                settings.groq_api_key,
                settings.groq_model,
                messages,
                json_mode=json_mode,
                reasoning_effort=reasoning_effort,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}"[:300])
    if settings.cerebras_api_key and settings.cerebras_model:
        try:
            return _try_provider(
                CEREBRAS_URL,
                settings.cerebras_api_key,
                settings.cerebras_model,
                messages,
                json_mode=json_mode,
                reasoning_effort=reasoning_effort,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}"[:300])
    raise LLMError("; ".join(errors) or "language model providers failed")


def complete_json(
    system: str,
    user: str,
    *,
    reasoning_effort: str | None = None,
    max_tokens: int | None = None,
) -> dict:
    raw = complete(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        json_mode=True,
        reasoning_effort=reasoning_effort,
        max_tokens=max_tokens,
    )
    return json.loads(raw)
