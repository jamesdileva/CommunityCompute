"""Upload bandwidth accounting (Sprint 25): rolling-window throttle.

Every work cycle records the bytes it sent (claim request + result POST
bodies, as measured by the caller). When the trailing 60s total would
exceed `policy.bandwidth_mbps`, the gate denies with a reason and the
worker skips claiming — the same fail-closed shape as every other policy
condition (Sprint 11 engine consumes this via `over_budget()`).

Prototype honesty: payloads here are KB-scale, so caps in the single-digit
Mbps range effectively never trip on real traffic. The mechanism (account,
window, throttle, reason) is what's proven; the numbers start to matter
once artifacts grow (model distribution and beyond).
"""

from __future__ import annotations

import time
from collections import deque


class BandwidthLedger:
    """Rolling byte counter. `now_fn` injectable for deterministic tests."""

    WINDOW_SECONDS = 60.0

    def __init__(self, now_fn=time.monotonic) -> None:
        self._now_fn = now_fn
        self._events: deque[tuple[float, int]] = deque()

    def record(self, byte_count: int, at: float | None = None) -> None:
        """Record bytes sent at time `at` (default: now)."""
        if byte_count < 0:
            raise ValueError("byte_count must be non-negative")
        now = self._now_fn() if at is None else at
        self._events.append((now, byte_count))
        self._prune(now)

    def bytes_in_window(self, at: float | None = None) -> int:
        now = self._now_fn() if at is None else at
        cutoff = now - self.WINDOW_SECONDS
        while self._events and self._events[0][0] <= cutoff:
            self._events.popleft()
        return sum(size for _, size in self._events)

    def over_budget(self, cap_mbps: float | None, at: float | None = None) -> bool:
        """True when the trailing window already reaches the cap.

        No cap configured means never over — callers may still pass a
        ledger that reports everything, so the guard lives here too.
        """
        if cap_mbps is None:
            return False
        return self.bytes_in_window(at) >= cap_mbps * 1024 * 1024 / 8

    def _prune(self, now: float | None = None) -> None:
        now = self._now_fn() if now is None else now
        cutoff = now - self.WINDOW_SECONDS
        while self._events and self._events[0][0] <= cutoff:
            self._events.popleft()
