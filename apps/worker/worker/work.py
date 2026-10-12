"""Work distribution client (Sprint 6; Sprint 7: lease-aware claim + 409 tolerance)."""

import httpx


def claim_work(
    coordinator_url: str,
    worker_id: str,
    cached_models: list[str] | None = None,
    timeout: float = 5.0,
) -> dict | None:
    """POST /work/{worker_id}/claim — sweeps expired leases, then FIFO claims.

    `cached_models` lets the coordinator prefer units whose model this worker
    already has cached (Sprint 15 preference, not a gate).
    Returns the assignment (with lease fields) or None when no work is queued.
    """
    url = f"{coordinator_url.rstrip('/')}/work/{worker_id}/claim"
    resp = httpx.post(url, json={"cached_models": cached_models or []}, timeout=timeout)
    resp.raise_for_status()
    return resp.json() or None


def submit_result(
    coordinator_url: str, work_unit_id: str, result_payload: dict, timeout: float = 5.0
) -> dict:
    """POST /work/{work_unit_id}/result.

    409 means the unit was already completed elsewhere (duplicate execution
    or a late result after lease expiry) — caller treats that as handled.
    """
    url = f"{coordinator_url.rstrip('/')}/work/{work_unit_id}/result"
    resp = httpx.post(url, json=result_payload, timeout=timeout)
    if resp.status_code == 409:
        return {"status": "already_completed"}
    resp.raise_for_status()
    return resp.json()
