"""Policy store (Sprint 11): `policy.json` beside the worker ID file.

Contributor-defined, so it persists across restarts (a pause survives a
reboot by design). Corrupt files fall back to defaults — the worker must
never crash on bad config.
"""

from __future__ import annotations

import json
from pathlib import Path

from worker.policy.schema import AvailabilityPolicy

DEFAULT_FILENAME = "policy.json"


def policy_path(worker_id_file: Path) -> Path:
    return worker_id_file.with_name(DEFAULT_FILENAME)


def load_policy(path: Path) -> AvailabilityPolicy:
    """Load a policy file; missing or corrupt → defaults (never crash)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return AvailabilityPolicy()
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return AvailabilityPolicy()
    try:
        return AvailabilityPolicy.model_validate(data)
    except Exception:  # noqa: BLE001 - pydantic ValidationError and friends
        return AvailabilityPolicy()


def save_policy(path: Path, policy: AvailabilityPolicy) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(policy.model_dump_json(indent=2), encoding="utf-8")


def set_paused(path: Path, paused: bool) -> AvailabilityPolicy:
    policy = load_policy(path)
    policy = policy.model_copy(update={"paused": paused})
    save_policy(path, policy)
    return policy
