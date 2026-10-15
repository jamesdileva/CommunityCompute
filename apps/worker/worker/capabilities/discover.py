"""Capability discovery assembly (Sprint 3; Sprint 15: cached models)."""

from __future__ import annotations

from worker.capabilities.cpu import discover_cpu
from worker.capabilities.gpu.registry import detect_gpus
from worker.capabilities.os_info import discover_os
from worker.capabilities.ram import discover_ram
from worker.capabilities.schema import CapabilityProfile
from worker.execution.registry import supported_runtimes
from worker.models.cache import ModelCache, default_cache_dir


def cached_models() -> list[dict]:
    """Verifiable artifacts currently on disk (best-effort)."""
    try:
        return ModelCache(default_cache_dir()).list_cached()
    except OSError:
        return []


def discover_capabilities() -> CapabilityProfile:
    """Auto-detect this machine's profile. No manual hardware entry anywhere."""
    return CapabilityProfile(
        cpu=discover_cpu(),
        ram=discover_ram(),
        os=discover_os(),
        gpus=detect_gpus(),
        runtimes=supported_runtimes(),
        cached_models=cached_models(),
        sandbox=_sandbox_available(),
    )


def _sandbox_available() -> bool:
    try:
        from worker.sandbox import native

        return native.available()
    except Exception:  # noqa: BLE001 - discovery must never crash
        return False
