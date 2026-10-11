"""GPU detection registry (Sprint 3): ordered provider selection, never crashes.

Real providers run first; the UnknownProvider result is only appended when
nothing was detected (so the profile always has at least one GPU slot).
Deduplicates by model name: if nvidia-smi found a GPU, the Windows WMI pass
won't add a duplicate entry for the same card.
"""

from __future__ import annotations

from worker.capabilities.gpu.base import GPUProvider
from worker.capabilities.gpu.nvidia import NvidiaProvider
from worker.capabilities.gpu.unknown import UnknownProvider
from worker.capabilities.gpu.wmi import WindowsVideoControllerProvider
from worker.capabilities.schema import GPUInfo


def default_providers() -> list[GPUProvider]:
    return [
        NvidiaProvider(),
        WindowsVideoControllerProvider(),
    ]


def detect_gpus(providers: list[GPUProvider] | None = None) -> list[GPUInfo]:
    providers = providers if providers is not None else default_providers()
    gpus: list[GPUInfo] = []
    seen_models: set[str] = set()
    for provider in providers:
        try:
            if not provider.available():
                continue
            for gpu in provider.detect():
                key = gpu.model.lower()
                if key in seen_models:
                    continue
                seen_models.add(key)
                gpus.append(gpu)
        except Exception:  # noqa: BLE001 - a broken provider must not kill discovery
            continue
    return gpus or UnknownProvider().detect()
