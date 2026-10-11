"""NVIDIA GPU provider (Sprint 3): nvidia-smi query for name/VRAM/driver/utilization."""

from __future__ import annotations

import shutil
import subprocess

from worker.capabilities.gpu.base import GPUProvider
from worker.capabilities.schema import GPUInfo


class NvidiaProvider(GPUProvider):
    name = "nvidia-smi"

    def available(self) -> bool:
        return shutil.which("nvidia-smi") is not None

    def detect(self) -> list[GPUInfo]:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        gpus: list[GPUInfo] = []
        if out.returncode != 0 or not out.stdout.strip():
            return gpus
        for line in out.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            name, vram_raw, driver = parts[0], parts[1], parts[2]
            util = parts[3] if len(parts) > 3 and parts[3] != "" else None
            gpus.append(
                GPUInfo(
                    vendor="nvidia",
                    model=name,
                    vram_mb=_to_int(vram_raw),
                    driver=driver or None,
                    utilization_percent=_to_float(util),
                    source=self.name,
                )
            )
        return gpus


def _to_int(value: str | None) -> int | None:
    try:
        return int(float(value)) if value else None
    except (TypeError, ValueError):
        return None


def _to_float(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except (TypeError, ValueError):
        return None
