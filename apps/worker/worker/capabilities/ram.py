"""RAM discovery (Sprint 3): total + available."""

from __future__ import annotations

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

from worker.capabilities.schema import MemoryInfo


def discover_ram() -> MemoryInfo:
    if psutil is None:
        return MemoryInfo()
    try:
        vm = psutil.virtual_memory()
        return MemoryInfo(
            total_mb=round(vm.total / (1024 * 1024)),
            available_mb=round(vm.available / (1024 * 1024)),
        )
    except Exception:  # noqa: BLE001 - degraded fields, never crash
        return MemoryInfo()
