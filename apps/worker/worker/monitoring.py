"""Resource monitoring (Sprint 12).

One sample per tick feeds both telemetry and the policy gate — a single
nvidia-smi call and one CPU sample per tick, not one per consumer. The
coordinator's ResourceReport schema describes the same shape.
"""

from __future__ import annotations

import httpx

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

from worker.credentials import Credential, auth_headers
from worker.policy.state import MachineState, collect_state


def sample_resources() -> dict:
    """Full machine sample (state sampler + RAM); undetectable → None."""
    return build_report(collect_state())


def build_report(state: MachineState) -> dict:
    """Telemetry report derived from an already-collected MachineState."""
    ram = psutil.virtual_memory() if psutil else None
    return {
        "cpu_percent": state.cpu_percent,
        "ram_available_mb": round(ram.available / (1024 * 1024)) if ram else None,
        "ram_used_percent": round(ram.percent, 1) if ram else None,
        "gpu_percent": state.gpu_percent,
        "gpu_vram_used_mb": (
            int(state.gpu_vram_used_mb)
            if isinstance(state.gpu_vram_used_mb, (int, float))
            else None
        ),
        "gpu_temp_c": state.gpu_temp_c,
    }


def report_resources(
    coordinator_url: str, worker_id: str, report: dict, timeout: float = 5.0,
    verify: bool | str = True, credential: Credential | None = None,
) -> dict | None:
    """POST the sample. Returns the stored row; None on failure (never raises)."""
    url = f"{coordinator_url.rstrip('/')}/workers/{worker_id}/resources"
    try:
        resp = httpx.post(url, json=report, timeout=timeout, verify=verify,
                          headers=auth_headers(credential))
        resp.raise_for_status()
        return resp.json()
    except Exception:  # noqa: BLE001 - telemetry must never break the loop
        return None
