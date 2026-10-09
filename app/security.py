"""Admin token check and a simple per-IP rate limit."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings

_HITS: dict[str, deque[float]] = defaultdict(deque)
LIMIT = 20
WINDOW_SECONDS = 60.0


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    now = time.time()
    bucket = _HITS[client_ip(request)]
    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests")
    bucket.append(now)


def enforce_admin(request: Request) -> None:
    expected = get_settings().admin_token
    provided = request.headers.get("x-admin-token", "")
    if not expected or provided != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
