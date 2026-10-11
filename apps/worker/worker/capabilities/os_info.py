"""OS discovery (Sprint 3)."""

from __future__ import annotations

import platform

from worker.capabilities.schema import OSInfo


def discover_os() -> OSInfo:
    return OSInfo(system=platform.system(), release=platform.release(), version=platform.version())
