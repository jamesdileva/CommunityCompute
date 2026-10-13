"""Capability report client (Sprint 3): POST /workers/{id}/capabilities."""

import httpx


def build_capability_payload(profile) -> dict:
    """Pydantic model -> JSON-safe dict (nested models included)."""
    return profile.model_dump()


def report_capabilities(
    coordinator_url: str, worker_id: str, profile, timeout: float = 5.0,
    verify: bool | str = True,
) -> dict:
    url = f"{coordinator_url.rstrip('/')}/workers/{worker_id}/capabilities"
    resp = httpx.post(url, json=build_capability_payload(profile), timeout=timeout,
                      verify=verify)
    resp.raise_for_status()
    return resp.json()
