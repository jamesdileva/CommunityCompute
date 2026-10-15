"""Capability estimate in plain language (Sprint 25 onboarding).

Tiers (H1/H2/H3) are engineer-facing; a new contributor needs to know what
their machine can *do*. This module translates a discovered profile into a
short human summary plus a contribution class the wizard and dashboard show.

The class is descriptive, never a promise: actual throughput is measured
from real units (execution_ms), and the scheduler — not this text — decides
routing (Sprints 9/31).
"""

from __future__ import annotations


def contribution_class(tiers: dict | None) -> str:
    """One of: gpu-capable / mixed / cpu-only / unknown."""
    if not tiers:
        return "unknown"
    gpu = (tiers or {}).get("gpu")
    cpu = (tiers or {}).get("cpu")
    if gpu in ("H2", "H3"):
        return "gpu-capable"
    if gpu == "H1" or cpu in ("H2", "H3"):
        return "mixed"
    if cpu == "H1":
        return "cpu-only"
    return "unknown"


def plain_language_summary(profile: dict, tiers: dict | None) -> list[str]:
    """Bullet lines for the wizard/dashboard. Pure data in, strings out."""
    lines: list[str] = []
    cpu = profile.get("cpu") or {}
    cores = cpu.get("physical_cores") or cpu.get("logical_cores") or "?"
    lines.append(f"CPU: {cores} cores ({_tier_word((tiers or {}).get('cpu'))})")
    ram_mb = (profile.get("ram") or {}).get("total_mb")
    lines.append(f"RAM: {_mb(ram_mb)} ({_tier_word((tiers or {}).get('ram'))})")
    gpus = profile.get("gpus") or []
    if not gpus:
        lines.append("GPU: none detected — CPU work only")
    else:
        for gpu in gpus:
            vendor = gpu.get("vendor", "unknown")
            model = gpu.get("model", "unknown")
            lines.append(f"GPU: {vendor} {model} "
                         f"{_mb(gpu.get('vram_mb'))} VRAM ({_tier_word((tiers or {}).get('gpu'))})")
    runtimes = profile.get("runtimes") or []
    lines.append(f"Can run: {', '.join(runtimes) if runtimes else 'nothing yet'}")
    cached = profile.get("cached_models") or []
    lines.append(f"Models cached: {len(cached)}")
    lines.append(f"Contribution class: {contribution_class(tiers)}")
    return lines


def workload_fit_note(workload_type: str, tiers: dict | None) -> str:
    """One-liner per workload class for the estimate step."""
    cls = contribution_class(tiers)
    table = {
        "hello_compute": "runs on any class (tiny CPU batches)",
        "stats_range": "runs on any class (tiny CPU batches)",
        "embeddings": (
            "runs on any class; faster with more cores "
            "(batches are CPU-bound here)"
        ),
    }
    note = table.get(workload_type, "unknown workload")
    return f"{workload_type}: {note} — your class: {cls}"


def _tier_word(tier: object) -> str:
    return {"H1": "modest", "H2": "mid-range", "H3": "strong"}.get(tier, "unknown")  # type: ignore[return-value]


def _mb(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "?"
    return f"{value / 1024:.1f} GB" if value >= 1024 else f"{int(value)} MB"
