"""Collect hardware baseline for Sprint 0 (record CPU/RAM/GPU for both PCs).

Usage:
    python scripts/collect_baseline.py [--out docs/baseline-<hostname>.json]

No manual hardware entry allowed (roadmap Sprint 3 rule) — this script is the source of truth.
GPU discovery uses adapter-style fallbacks: nvidia-smi → Win32_VideoController → Unknown.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


def cpu_info() -> dict:
    info: dict = {
        "arch": platform.machine(),
        "processor": platform.processor(),
    }
    if psutil:
        try:
            info["logical_cores"] = psutil.cpu_count(logical=True)
            info["physical_cores"] = psutil.cpu_count(logical=False)
            freq = psutil.cpu_freq()
            if freq:
                info["freq_mhz"] = {"current": freq.current, "max": freq.max}
        except Exception as exc:  # noqa: BLE001
            info["psutil_error"] = str(exc)
    return info


def mem_info() -> dict:
    if not psutil:
        return {"error": "psutil not installed"}
    vm = psutil.virtual_memory()
    return {
        "total_mb": round(vm.total / (1024 * 1024)),
        "available_mb": round(vm.available / (1024 * 1024)),
    }


def gpu_info() -> list[dict]:
    """Best-effort GPU list. Never crashes — returns UnknownProvider entry if undetectable."""
    gpus: list[dict] = []
    # 1) nvidia-smi (best detail on NVIDIA)
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            if out.returncode == 0 and out.stdout.strip():
                for line in out.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 2:
                        gpus.append({
                            "vendor": "nvidia",
                            "model": parts[0],
                            "vram_mb": int(float(parts[1])),
                            "driver": parts[2] if len(parts) > 2 else None,
                            "source": "nvidia-smi",
                        })
                if gpus:
                    return gpus
        except Exception as exc:  # noqa: BLE001
            gpus.append({"vendor": "unknown", "source": "nvidia-smi", "error": str(exc)})
    # 2) Windows Win32_VideoController (covers Intel Iris Xe, AMD, etc.)
    if sys.platform == "win32":
        try:
            ps = (
                "Get-CimInstance Win32_VideoController | "
                "Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json"
            )
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=15,
            )
            if out.returncode == 0 and out.stdout.strip():
                data = json.loads(out.stdout.strip())
                if isinstance(data, dict):
                    data = [data]
                for entry in data:
                    name = (entry.get("Name") or "unknown").strip()
                    raw_ram = entry.get("AdapterRAM")
                    try:
                        vram_mb = round(int(raw_ram) / (1024 * 1024)) if raw_ram else None
                    except (TypeError, ValueError):
                        vram_mb = None
                    vendor = "intel" if "intel" in name.lower() else (
                        "nvidia" if "nvidia" in name.lower() else (
                            "amd" if "amd" in name.lower() or "radeon" in name.lower() else "unknown"))
                    gpus.append({
                        "vendor": vendor, "model": name, "vram_mb": vram_mb,
                        "driver": entry.get("DriverVersion"), "source": "Win32_VideoController",
                    })
                if gpus:
                    return gpus
        except Exception as exc:  # noqa: BLE001
            gpus.append({"vendor": "unknown", "source": "Win32_VideoController", "error": str(exc)})
    if not gpus:
        gpus.append({"vendor": "unknown", "model": "undetected", "source": "UnknownProvider"})
    return gpus


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Collect hardware baseline (Sprint 0)")
    p.add_argument("--out", default=None, help="Write JSON baseline to file")
    args = p.parse_args(argv)

    baseline = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "os": {"system": platform.system(), "release": platform.release(),
               "version": platform.version()},
        "python": platform.python_version(),
        "cpu": cpu_info(),
        "ram": mem_info(),
        "gpus": gpu_info(),
    }
    text = json.dumps(baseline, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
