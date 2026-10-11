"""Single-call GPU stats helper (Sprint 12).

One nvidia-smi query serves both the policy sampler and telemetry — drivers
without nvidia-smi (Intel/AMD here) report None for every metric.
"""

from __future__ import annotations

import shutil
import subprocess

_QUERY = "utilization.gpu,memory.used,temperature.gpu"


def query_gpu() -> dict[str, float | None]:
    """→ {"utilization_gpu", "memory_used_mb", "temperature_gpu"} (None if absent)."""
    empty = {"utilization_gpu": None, "memory_used_mb": None, "temperature_gpu": None}
    if not shutil.which("nvidia-smi"):
        return empty
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={_QUERY}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return empty
        parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
        while len(parts) < 3:
            parts.append("")
        return {
            "utilization_gpu": _to_float(parts[0]),
            "memory_used_mb": _to_int(parts[1]),
            "temperature_gpu": _to_float(parts[2]),
        }
    except (OSError, subprocess.SubprocessError):
        return empty


def _to_float(value: str) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _to_int(value: str) -> int | None:
    try:
        return int(float(value)) if value else None
    except ValueError:
        return None
