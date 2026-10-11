"""Windows GPU provider (Sprint 3): Win32_VideoController query (cross-vendor).

Covers Intel Iris Xe, AMD, and NVIDIA when nvidia-smi is absent. VRAM is
reported as uint32 by some drivers and caps at 4GB — record what WMI says;
adapter RAM beyond 4GB may be truncated (known WMI limitation, documented
rather than worked around in the prototype).
"""

from __future__ import annotations

import json
import sys

from worker.capabilities.gpu.base import GPUProvider
from worker.capabilities.schema import GPUInfo


class WindowsVideoControllerProvider(GPUProvider):
    name = "Win32_VideoController"

    def available(self) -> bool:
        return sys.platform == "win32"

    def detect(self) -> list[GPUInfo]:
        query = (
            "Get-CimInstance Win32_VideoController | "
            "Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json"
        )
        out = subprocess_run_powershell(query)
        if out is None:
            return []
        try:
            data = json.loads(out.strip())
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = [data]
        return [self._to_gpu(entry) for entry in data if isinstance(entry, dict)]

    def _to_gpu(self, entry: dict) -> GPUInfo:
        name = (entry.get("Name") or "unknown").strip()
        vendor = (
            "intel" if "intel" in name.lower()
            else "nvidia" if "nvidia" in name.lower()
            else "amd" if "amd" in name.lower() or "radeon" in name.lower()
            else "unknown"
        )
        return GPUInfo(
            vendor=vendor,
            model=name,
            vram_mb=_to_int(entry.get("AdapterRAM")),
            driver=entry.get("DriverVersion"),
            source=self.name,
        )


def _to_int(raw: object) -> int | None:
    try:
        return round(int(raw) / (1024 * 1024)) if raw else None
    except (TypeError, ValueError):
        return None


def subprocess_run_powershell(query: str) -> str | None:
    import subprocess

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", query],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None
