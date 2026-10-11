"""Sprint 3: CPU/RAM/OS discovery on this real machine (no manual entry)."""

import platform

from worker.capabilities.cpu import discover_cpu
from worker.capabilities.os_info import discover_os
from worker.capabilities.ram import discover_ram


def test_cpu_discovered():
    cpu = discover_cpu()
    assert cpu.arch == platform.machine()
    assert cpu.processor
    assert (cpu.logical_cores or 0) >= 1


def test_ram_discovered():
    ram = discover_ram()
    assert ram.total_mb and ram.total_mb > 0
    assert ram.available_mb is not None and ram.available_mb >= 0


def test_os_discovered():
    os_info = discover_os()
    assert os_info.system == platform.system()
    assert os_info.release
