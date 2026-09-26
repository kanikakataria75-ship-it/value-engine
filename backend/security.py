"""API protection: optional bearer-token auth and in-memory rate limiting.

Set VALUENGINE_API_TOKEN to require `Authorization: Bearer <token>` (or `X-API-Key: <token>`) on
every /api route except /api/health. Rate limits apply per client IP and protect the endpoints
that call paid LLM providers or run heavy simulations.
"""
from __future__ import annotations

from collections import defaultdict, deque
import hmac
import os
import threading
import time
from typing import Callable

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def rate_limit(bucket: str, per_minute: int) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(f"{bucket}:{client}", per_minute):
            raise HTTPException(status_code=429, detail=f"Rate limit exceeded: at most {per_minute} {bucket} requests per minute.")
    return dependency


def configured_token() -> str | None:
    return os.environ.get("VALUENGINE_API_TOKEN") or None


def is_authorized(request: Request) -> bool:
    token = configured_token()
    if token is None:
        return True
    header = request.headers.get("authorization", "")
    supplied = header[7:] if header.lower().startswith("bearer ") else request.headers.get("x-api-key", "")
    return bool(supplied) and hmac.compare_digest(supplied.encode(), token.encode())
