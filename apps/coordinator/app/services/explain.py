"""Compatibility explanation (Sprint 10).

Wraps `compat.check()` with a per-dimension breakdown so the scheduler can
answer *why* a work unit is or is not compatible with a worker — the
Sprint 10 exit condition made inspectable (dashboard/SRE view).
"""

from __future__ import annotations

from app.services.compat import check


def explain(requirements: dict | None, profile: dict | None) -> dict:
    """Per-check rows + overall verdict. Never raises on odd shapes."""
    reqs = {k: v for k, v in (requirements or {}).items() if v not in (None, False)}
    if not reqs:
        return {
            "compatible": True,
            "reason": "no requirements",
            "checks": [],
        }
    if not profile:
        return {
            "compatible": False,
            "reason": "no capabilities reported",
            "checks": [],
        }

    rows = [
        _cpu_row(reqs, profile),
        _ram_row(reqs, profile),
        _os_row(reqs, profile),
        _runtime_row(reqs, profile),
        _gpu_row(reqs, profile),
    ]
    rows = [r for r in rows if r is not None]
    ok, reason = check(reqs, profile)
    return {"compatible": ok, "reason": reason, "checks": rows}


def _cpu_row(reqs: dict, profile: dict) -> dict | None:
    if "cpu_cores" not in reqs:
        return None
    have = (profile.get("cpu") or {}).get("logical_cores")
    need = reqs["cpu_cores"]
    return _row("cpu_cores", need, have, have is not None and have >= need)


def _ram_row(reqs: dict, profile: dict) -> dict | None:
    if "ram_mb" not in reqs:
        return None
    have = (profile.get("ram") or {}).get("total_mb")
    need = reqs["ram_mb"]
    return _row("ram_mb", need, have, have is not None and have >= need)


def _os_row(reqs: dict, profile: dict) -> dict | None:
    if "os" not in reqs:
        return None
    need = reqs["os"]
    have = (profile.get("os") or {}).get("system")
    passed = bool(have) and str(have).lower() == str(need).lower()
    return _row("os", need, have, passed)


def _runtime_row(reqs: dict, profile: dict) -> dict | None:
    if "runtime" not in reqs:
        return None
    need = reqs["runtime"]
    have = profile.get("runtimes") or []
    return _row("runtime", need, have, need in have)


def _gpu_row(reqs: dict, profile: dict) -> dict | None:
    if not reqs.get("gpu"):
        return None
    need_vendor = reqs.get("gpu_vendor")
    need_vram = reqs.get("min_vram_mb")
    gpus = profile.get("gpus") or []
    matched = None
    for gpu in gpus:
        if need_vendor and str(gpu.get("vendor", "")).lower() != str(need_vendor).lower():
            continue
        if need_vram is not None:
            have_vram = gpu.get("vram_mb")
            if have_vram is None or have_vram < need_vram:
                continue
        matched = gpu
        break
    have = matched or {"gpus": [g.get("model") for g in gpus]}
    need = {"vendor": need_vendor, "min_vram_mb": need_vram}
    return _row("gpu", need, have, matched is not None)


def _row(dimension: str, need: object, have: object, passed: bool) -> dict:
    return {
        "dimension": dimension,
        "need": need,
        "have": have,
        "passed": passed,
        "reason": "ok" if passed else _why(dimension, need, have),
    }


def _why(dimension: str, need: object, have: object) -> str:
    return f"{dimension}: need {need!r}, have {have!r}"
