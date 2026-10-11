"""Machine state sampling for policy evaluation (Sprint 11; Sprint 12: one GPU query).

Measurable signals only (implementation-guide §17): CPU/GPU utilization,
temperature, battery, input idle. Anything undetectable is reported as
None — the engine then decides (fail closed where safety demands).
"""

from __future__ import annotations

import sys
from datetime import datetime

try:
    import psutil
except ImportError:  # pragma: no cover - hard dependency
    psutil = None

from worker.gpu_stats import query_gpu


class MachineState:
    """Snapshot: None means "unknown on this machine", never a guess."""

    def __init__(
        self,
        cpu_percent: float | None,
        gpu_percent: float | None,
        gpu_temp_c: float | None,
        on_battery: bool | None,
        idle_seconds: float | None,
        gpu_vram_used_mb: float | None = None,
        now: datetime | None = None,
    ) -> None:
        self.cpu_percent = cpu_percent
        self.gpu_percent = gpu_percent
        self.gpu_temp_c = gpu_temp_c
        self.on_battery = on_battery
        self.idle_seconds = idle_seconds
        self.gpu_vram_used_mb = gpu_vram_used_mb
        self.now = now or datetime.now()


def collect_state() -> MachineState:
    gpu = query_gpu()
    return MachineState(
        cpu_percent=_cpu_percent(),
        gpu_percent=gpu["utilization_gpu"],
        gpu_temp_c=gpu["temperature_gpu"],
        on_battery=_on_battery(),
        idle_seconds=_idle_seconds(),
        gpu_vram_used_mb=gpu["memory_used_mb"],
    )


def _cpu_percent() -> float | None:
    if psutil is None:
        return None
    try:
        return round(psutil.cpu_percent(interval=0.2), 1)
    except Exception:  # noqa: BLE001
        return None


def _on_battery() -> bool | None:
    if psutil is None:
        return None
    try:
        battery = psutil.sensors_battery()
        return None if battery is None else not battery.power_plugged
    except Exception:  # noqa: BLE001
        return None


def _idle_seconds() -> float | None:
    """Seconds since last input (Windows GetLastInputInfo); None on other platforms."""
    if sys.platform != "win32":
        return None

    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):  # type: ignore[attr-defined]
        return None
    uptime_ms = ctypes.windll.kernel32.GetTickCount()  # type: ignore[attr-defined]
    return max(0.0, (uptime_ms - lii.dwTime) / 1000.0)
