"""Capability discovery assembly (Sprint 3)."""

from __future__ import annotations

from worker.capabilities.cpu import discover_cpu
from worker.capabilities.gpu.registry import detect_gpus
from worker.capabilities.os_info import discover_os
from worker.capabilities.ram import discover_ram
from worker.capabilities.schema import CapabilityProfile


def discover_capabilities() -> CapabilityProfile:
    """Auto-detect this machine's profile. No manual hardware entry anywhere."""
    return CapabilityProfile(
        cpu=discover_cpu(),
        ram=discover_ram(),
        os=discover_os(),
        gpus=detect_gpus(),
    )
