"""CPU discovery (Sprint 3): architecture, cores, approximate frequency."""

from __future__ import annotations

import platform

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is a hard dependency
    psutil = None

from worker.capabilities.schema import CPUInfo


def discover_cpu() -> CPUInfo:
    info = CPUInfo(arch=platform.machine(), processor=platform.processor())
    if psutil is None:
        return info
    try:
        info.logical_cores = psutil.cpu_count(logical=True)
    except Exception:  # noqa: BLE001 - degraded field, never crash
        pass
    try:
        info.physical_cores = psutil.cpu_count(logical=False)
    except Exception:  # noqa: BLE001
        pass
    try:
        freq = psutil.cpu_freq()
        if freq:
            info.freq_mhz = freq.max or freq.current
    except Exception:  # noqa: BLE001
        pass
    return info
