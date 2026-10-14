"""Heartbeat client (Sprint 4): liveness + runtime resource snapshot."""

import shutil
import subprocess

import httpx

from worker.credentials import Credential, auth_headers

try:
    import psutil
except ImportError:  # pragma: no cover - hard dependency
    psutil = None


def build_heartbeat_payload(worker_id: str) -> dict:
    """Cheap local snapshot: CPU %, available RAM MB, GPU % when nvidia-smi exists."""
    return {
        "worker_id": worker_id,
        "resources": {
            "cpu_percent": _cpu_percent(),
            "ram_available_mb": _ram_available_mb(),
            "gpu_percent": _gpu_percent(),
        },
    }


def send_heartbeat(
    coordinator_url: str, payload: dict, timeout: float = 5.0,
    verify: bool | str = True, credential: Credential | None = None,
) -> dict:
    """POST /workers/{id}/heartbeat. Raises on failure (caller logs/retries)."""
    wid = payload["worker_id"]
    url = f"{coordinator_url.rstrip('/')}/workers/{wid}/heartbeat"
    resp = httpx.post(url, json=payload, timeout=timeout, verify=verify,
                      headers=auth_headers(credential))
    resp.raise_for_status()
    return resp.json()


def _cpu_percent() -> float | None:
    if psutil is None:
        return None
    try:
        value = psutil.cpu_percent(interval=0.2)  # short sample for a real reading
        return round(value, 1)
    except Exception:  # noqa: BLE001 - degraded telemetry
        return None


def _ram_available_mb() -> int | None:
    if psutil is None:
        return None
    try:
        return round(psutil.virtual_memory().available / (1024 * 1024))
    except Exception:  # noqa: BLE001
        return None


def _gpu_percent() -> float | None:
    """GPU utilization via nvidia-smi when present; None otherwise (Iris Xe: no utilizer in prototype)."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return float(out.stdout.strip().splitlines()[0].strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return None
