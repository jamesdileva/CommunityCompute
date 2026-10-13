"""Worker config: coordinator URL + persistent worker ID.

Sprint 0: minimal ping only. Sprint 2 adds full registration.
Identity rule (implementation-guide §7): persistent generated UUID, never hostname.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def get_coordinator_url(explicit: str | None = None) -> str:
    if explicit:
        return explicit.rstrip("/")
    return os.environ.get("COORDINATOR_URL", "http://127.0.0.1:8000").rstrip("/")


def get_worker_id_file(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    return Path(os.environ.get("WORKER_ID_FILE", ".worker_id"))


def get_tls_verify(
    ca_bundle: str | None = None, insecure: bool = False
) -> bool | str:
    """httpx `verify` argument for TLS (Sprint 19).

    `insecure=True` disables verification (dev self-signed certs only —
    callers must print a loud warning). Otherwise a `--ca-bundle` path or
    the platform trust store (`True`). Auth is out of scope (Sprint 20):
    this is transport trust only.
    """
    if insecure:
        return False
    return ca_bundle or True


def get_or_create_worker_id(id_file: Path) -> str:
    """Load persistent UUID or create+store one. Never derives identity from hostname."""
    if id_file.exists():
        text = id_file.read_text(encoding="utf-8").strip()
        if text:
            try:
                return str(uuid.UUID(text))
            except ValueError:
                pass  # corrupt file → regenerate below
    new_id = str(uuid.uuid4())
    id_file.parent.mkdir(parents=True, exist_ok=True)
    id_file.write_text(new_id, encoding="utf-8")
    return new_id
