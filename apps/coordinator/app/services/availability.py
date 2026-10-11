"""Availability derivation (Sprint 4).

A worker is online when its `last_seen` is fresh relative to the configured
heartbeat timeout. Explicit states (paused/disabled) win when they exist
(Sprint 11+). The worker never declares itself online authoritatively —
silence means offline.
"""

from datetime import datetime, timedelta, timezone

from app.models.worker import OFFLINE, ONLINE, Worker

# States set explicitly (not derived): paused by contributor policy (Sprint 11),
# disabled by an operator. Unknown until first heartbeat/registration.
_EXPLICIT = {"paused", "disabled"}


def effective_status(worker: Worker, timeout_seconds: int) -> str:
    if worker.status in _EXPLICIT:
        return worker.status
    if worker.last_seen is None:
        return OFFLINE
    last = _aware(worker.last_seen)
    return ONLINE if datetime.now(timezone.utc) - last <= timedelta(seconds=timeout_seconds) else OFFLINE


def _aware(dt: datetime) -> datetime:
    """Treat naive datetimes (SQLite server defaults) as UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
