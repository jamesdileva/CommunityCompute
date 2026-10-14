"""Worker credential storage + enrollment (Sprint 20).

The coordinator mints an enrollment token (operator); the worker exchanges
it here for a long-lived bearer credential: `worker_id` + `token`. Both are
persisted to `credential.json` beside the worker ID file — the only place
the raw token ever exists. From then on every HTTP call and the WebSocket
URL carry it (`Authorization: Bearer <token>` / `?token=`).

With `AUTH_ENABLED=false` (coordinator default) the whole file is optional:
missing credential → no headers → anonymous LAN flow keeps working.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import httpx


@dataclass(frozen=True)
class Credential:
    worker_id: str
    token: str


def credential_path(worker_id_file: Path) -> Path:
    return worker_id_file.with_name("credential.json")


def load_credential(worker_id_file: Path) -> Credential | None:
    """Load the saved credential; missing/corrupt/incomplete → None (never raises)."""
    path = credential_path(worker_id_file)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    worker_id = data.get("worker_id")
    token = data.get("token")
    if not worker_id or not token:
        return None
    return Credential(worker_id=str(worker_id), token=str(token))


def save_credential(worker_id_file: Path, credential: Credential) -> None:
    path = credential_path(worker_id_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"worker_id": credential.worker_id, "token": credential.token}, indent=2),
        encoding="utf-8",
    )


def auth_headers(credential: Credential | None) -> dict[str, str]:
    """Authorization header dict; empty when no credential."""
    if credential is None:
        return {}
    return {"Authorization": f"Bearer {credential.token}"}


def enroll(
    coordinator_url: str,
    enrollment_token: str,
    timeout: float = 5.0,
    verify: bool | str = True,
) -> Credential:
    """Exchange an enrollment token for a worker credential (POST /auth/enroll).

    Raises httpx.HTTPStatusError on 401/404 (bad or already-used token) so
    the CLI can report the coordinator's reason.
    """
    url = f"{coordinator_url.rstrip('/')}/auth/enroll"
    resp = httpx.post(
        url, json={"enrollment_token": enrollment_token}, timeout=timeout, verify=verify
    )
    resp.raise_for_status()
    body = resp.json()
    credential = Credential(worker_id=body["worker_id"], token=body["token"])
    return credential
