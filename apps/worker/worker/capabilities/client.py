"""Capability report client (Sprint 3): POST /workers/{id}/capabilities."""

import httpx

from worker.credentials import Credential, auth_headers


def build_capability_payload(profile) -> dict:
    """Pydantic model -> JSON-safe dict (nested models included)."""
    return profile.model_dump()


def report_capabilities(
    coordinator_url: str, worker_id: str, profile, timeout: float = 5.0,
    verify: bool | str = True, credential: Credential | None = None,
) -> dict:
    url = f"{coordinator_url.rstrip('/')}/workers/{worker_id}/capabilities"
    resp = httpx.post(url, json=build_capability_payload(profile), timeout=timeout,
                      verify=verify, headers=auth_headers(credential))
    resp.raise_for_status()
    return resp.json()
