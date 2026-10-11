"""Compatibility filter (Sprint 9): workload requirements × worker capabilities.

Declarative matching per implementation-guide §10 — the scheduler never has
workload-specific branching; it asks `check()` whether a worker's stored
profile satisfies a job's requirements. Order follows architecture §10:
CPU → RAM → OS → runtime → GPU (vendor/VRAM).

Convention: an *empty* requirement set runs anywhere (backwards compatible
with unrestricted jobs/workers). A non-empty set with *no reported profile*
is incompatible — we don't send work we can't prove fits (fail closed).
"""

from __future__ import annotations


def check(requirements: dict | None, capabilities: dict | None) -> tuple[bool, str]:
    """Return (compatible, reason). Never raises on odd shapes — rejects instead."""
    reqs = {k: v for k, v in (requirements or {}).items() if v not in (None, False)}
    if not reqs:
        return True, "no requirements"
    if not capabilities:
        return False, "no capabilities reported"

    cpu = (capabilities.get("cpu") or {})
    need_cores = reqs.get("cpu_cores")
    if need_cores is not None:
        have = cpu.get("logical_cores")
        if have is None or have < need_cores:
            return False, f"cpu_cores: need {need_cores}, have {have}"

    ram = (capabilities.get("ram") or {})
    need_ram = reqs.get("ram_mb")
    if need_ram is not None:
        have = ram.get("total_mb")
        if have is None or have < need_ram:
            return False, f"ram_mb: need {need_ram}, have {have}"

    need_os = reqs.get("os")
    if need_os is not None:
        have = (capabilities.get("os") or {}).get("system")
        if not have or have.lower() != str(need_os).lower():
            return False, f"os: need {need_os!r}, have {have!r}"

    need_runtime = reqs.get("runtime")
    if need_runtime is not None:
        runtimes = capabilities.get("runtimes") or []
        if need_runtime not in runtimes:
            return False, f"runtime {need_runtime!r} not advertised"

    if reqs.get("gpu"):
        gpus = capabilities.get("gpus") or []
        vendor = reqs.get("gpu_vendor")
        min_vram = reqs.get("min_vram_mb")
        for gpu in gpus:
            if vendor is not None and str(gpu.get("vendor", "")).lower() != str(vendor).lower():
                continue
            if min_vram is not None:
                have_vram = gpu.get("vram_mb")
                if have_vram is None or have_vram < min_vram:
                    continue
            return True, "gpu requirement satisfied"
        want = f"vendor={vendor} min_vram={min_vram}"
        return False, f"no compatible gpu ({want}; worker has {len(gpus)} gpu entries)"

    return True, "compatible"
