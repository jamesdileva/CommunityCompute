"""Work distribution client (Sprint 6): claim → execute → submit result."""

import httpx


def claim_work(coordinator_url: str, worker_id: str, timeout: float = 5.0) -> dict | None:
    """GET /work/{worker_id}. None when nothing is queued (empty body)."""
    url = f"{coordinator_url.rstrip('/')}/work/{worker_id}"
    resp = httpx.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json() or None


def submit_result(
    coordinator_url: str, work_unit_id: str, result_payload: dict, timeout: float = 5.0
) -> dict:
    """POST /work/{work_unit_id}/result. Raises on 4xx/5xx (caller logs + moves on)."""
    url = f"{coordinator_url.rstrip('/')}/work/{work_unit_id}/result"
    resp = httpx.post(url, json=result_payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()
