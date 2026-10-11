"""GPU provider interface (Sprint 3).

Adapter pattern per implementation-guide §8:
    GPUProvider
    ├── NvidiaProvider      (nvidia-smi)
    ├── WindowsVideoController (Win32_VideoController, cross-vendor)
    └── UnknownProvider      (never crash)

Providers return GPUInfo; the registry picks the best available provider
for each detected GPU.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from worker.capabilities.schema import GPUInfo


class GPUProvider(ABC):
    """Detects one class of GPU. Must never raise — degrade instead."""

    name: str = "base"

    @abstractmethod
    def available(self) -> bool:
        """True when this provider's detection mechanism exists on this machine."""

    @abstractmethod
    def detect(self) -> list[GPUInfo]:
        """Return detected GPUs (empty list when nothing found). Must not raise."""
