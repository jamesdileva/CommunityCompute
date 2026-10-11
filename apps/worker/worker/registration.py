"""Registration client (Sprint 2).

Sends the WorkerRegistration message (protocol sketch, implementation-guide §4):
worker_id (persistent UUID) + worker_version + hostname (metadata only, never identity).
"""

import socket

import httpx

from worker import __version__ as WORKER_VERSION


def build_payload(
    worker_id: str, version: str = WORKER_VERSION, hostname: str | None = None
) -> dict:
    return {
        "worker_id": worker_id,
        "worker_version": version,
        "hostname": hostname or socket.gethostname(),
    }


def register_worker(coordinator_url: str, payload: dict, timeout: float = 5.0) -> dict:
    """POST /workers/register. Returns the coordinator's worker record. Raises on failure."""
    url = f"{coordinator_url.rstrip('/')}/workers/register"
    resp = httpx.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()
