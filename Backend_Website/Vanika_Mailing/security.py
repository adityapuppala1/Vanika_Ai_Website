# Vanika_Mailing/security.py
import secrets
import time
from collections import deque
from typing import Deque, Dict

# pyrefly: ignore [missing-import]
from fastapi import Header, HTTPException, Request
from config import settings


class RateLimiter:
    """In-memory sliding-window limiter, keyed by client IP.

    Per-process only: with several App Service instances each one keeps its own
    window, which is acceptable for spam protection on a waitlist form.
    """

    MAX_KEYS = 10_000

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = {}

    def _expire(self, hits: Deque[float], now: float) -> None:
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()

    def _prune(self, now: float) -> None:
        # Bound memory: drop keys whose window has fully expired
        for key in list(self._hits):
            self._expire(self._hits[key], now)
            if not self._hits[key]:
                del self._hits[key]

    def is_limited(self, key: str) -> bool:
        hits = self._hits.get(key)
        if not hits:
            return False
        self._expire(hits, time.monotonic())
        return len(hits) >= self.max_requests

    def allow(self, key: str) -> bool:
        """Record a hit; False when the key is already over the limit."""
        now = time.monotonic()
        if key not in self._hits and len(self._hits) >= self.MAX_KEYS:
            self._prune(now)
        hits = self._hits.setdefault(key, deque())
        self._expire(hits, now)
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


subscribe_limiter = RateLimiter(settings.VANIKA_SUBSCRIBE_RATE_LIMIT, 60)
admin_failure_limiter = RateLimiter(10, 300)


def client_ip(request: Request) -> str:
    # Azure's front end *appends* the real client address to X-Forwarded-For, so
    # only the last entry is trustworthy — earlier ones are whatever the client sent.
    # Entries look like "ip:port" (IPv4) or "[ip]:port" (IPv6).
    forwarded = request.headers.get("x-forwarded-for", "")
    last = forwarded.split(",")[-1].strip()
    if last:
        if last.startswith("["):
            return last[1:].split("]")[0]
        if last.count(":") == 1:
            return last.split(":")[0]
        return last
    return request.client.host if request.client else "unknown"


async def require_admin(request: Request, x_admin_key: str = Header(default="")) -> None:
    if not settings.VANIKA_ADMIN_KEY:
        raise HTTPException(status_code=503, detail="ADMIN_DISABLED: set VANIKA_ADMIN_KEY on the server")

    ip = client_ip(request)
    # Check the lockout before comparing, so a locked-out client cannot keep guessing
    if admin_failure_limiter.is_limited(ip):
        raise HTTPException(status_code=429, detail="TOO_MANY_ATTEMPTS")
    if secrets.compare_digest(x_admin_key.encode(), settings.VANIKA_ADMIN_KEY.encode()):
        return
    admin_failure_limiter.allow(ip)
    raise HTTPException(status_code=401, detail="INVALID_ADMIN_KEY")
