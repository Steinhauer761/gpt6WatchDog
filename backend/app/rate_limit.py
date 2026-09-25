from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: int
    retry_after: int


class FixedWindowRateLimiter:
    """Small, dependency-free limiter for a single application process.

    Identities are hashed before storage so bearer tokens and client addresses are
    never retained in memory as plain text. The entry cap also prevents a stream
    of fabricated identities from growing the process indefinitely.
    """

    def __init__(
        self,
        *,
        max_entries: int = 20_000,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._max_entries = max(100, int(max_entries))
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[tuple[str, str, int], int] = {}
        self._calls = 0

    @staticmethod
    def _identity_digest(identity: str) -> str:
        return hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()

    def consume(self, bucket: str, identity: str, limit: int, window_seconds: int) -> RateLimitResult:
        safe_limit = max(1, int(limit))
        safe_window = max(1, int(window_seconds))
        now = int(self._clock())
        reset_at = ((now // safe_window) + 1) * safe_window
        digest = self._identity_digest(identity or "anonymous")
        key = (bucket, digest, reset_at)

        with self._lock:
            self._calls += 1
            if self._calls % 256 == 0 or len(self._entries) >= self._max_entries:
                self._entries = {
                    entry_key: count
                    for entry_key, count in self._entries.items()
                    if entry_key[2] > now
                }

            if key not in self._entries and len(self._entries) >= self._max_entries:
                # New identities share a conservative overflow bucket until the
                # current window expires instead of consuming unbounded memory.
                key = (bucket, "overflow", reset_at)

            count = self._entries.get(key, 0)
            allowed = count < safe_limit
            if allowed:
                count += 1
                self._entries[key] = count

        return RateLimitResult(
            allowed=allowed,
            limit=safe_limit,
            remaining=max(0, safe_limit - count),
            reset_at=reset_at,
            retry_after=max(1, reset_at - now),
        )

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._calls = 0
