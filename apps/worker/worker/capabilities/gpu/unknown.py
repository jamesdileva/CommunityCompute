"""Unknown GPU provider (Sprint 3): guarantees a capability record exists."""

from __future__ import annotations

from worker.capabilities.gpu.base import GPUProvider
from worker.capabilities.schema import GPUInfo


class UnknownProvider(GPUProvider):
    name = "UnknownProvider"

    def available(self) -> bool:
        return True

    def detect(self) -> list[GPUInfo]:
        return [GPUInfo(vendor="unknown", model="undetected", source=self.name)]
