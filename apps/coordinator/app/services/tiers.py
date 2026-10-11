"""Hardware tier normalization (Sprint 10, architecture §5).

H1 low-end/constrained, H2 mid-range, H3 high-end — normalized *per
resource* (GPU, CPU, RAM) so the scheduler matches actual strengths instead
of a global "power score" (architecture §5). Tiers are coarse classes for
routing explanations; the numeric `score()` stubs the later scoring model
(Sprint 31) and is exported but not wired into scheduling yet.
"""

from __future__ import annotations

H1 = "H1"
H2 = "H2"
H3 = "H3"
UNKNOWN = "unknown"


def _band(value: float | None, *, low: float, high: float) -> str:
    """`low`/`high` BANDS: <=low H1, low<value<=high H2, >high H3.

    Boundary convention: the band label covers the lower bound inclusively
    (e.g. a 4GB GPU is H2's floor because 4GB is H2's minimum).
    """
    if value is None:
        return H1
    if value <= low:
        return H1
    if value <= high:
        return H2
    return H3


def gpu_tier(gpu: dict | None) -> str | None:
    """Tier for one GPU: VRAM bands; integrated/undetected → H1."""
    if not gpu:
        return None
    vendor = str(gpu.get("vendor", "")).lower()
    vram = gpu.get("vram_mb")
    if vram is None:
        return H1  # integrated or undetected → constrained tier
    if vendor == "intel":
        return H1  # integrated graphics: shared-memory ceiling
    return _band(vram, low=4096, high=12288)  # <=4GB H1 · 4-12GB H2 · >12GB H3


def cpu_tier(cpu: dict | None) -> str:
    cores = (cpu or {}).get("physical_cores") or (cpu or {}).get("logical_cores")
    if cores is None:
        return UNKNOWN
    return _band(cores, low=4, high=8)


def ram_tier(ram: dict | None) -> str:
    total_mb = (ram or {}).get("total_mb")
    if total_mb is None:
        return UNKNOWN
    total_gb = total_mb / 1024
    if total_gb <= 8:
        return H1
    if total_gb <= 32:
        return H2
    return H3


def hardware_tiers(profile: dict | None) -> dict:
    """Per-axis tiers for a worker profile ({} when no profile at all)."""
    if not profile:
        return {}
    gpus = profile.get("gpus") or []
    gpu_tiers = [t for t in (gpu_tier(g) for g in gpus) if t]
    order = {H3: 3, H2: 2, H1: 1}
    best = max(gpu_tiers, key=lambda t: order.get(t, 0)) if gpu_tiers else None
    return {
        "gpu": best,
        "cpu": cpu_tier(profile.get("cpu")),
        "ram": ram_tier(profile.get("ram")),
    }


# --- Sprint 31 scoring stubs (exported, not yet wired into scheduling) -------
# These intentionally mirror the architecture §10 score inputs so the
# scheduler can adopt them wholesale once correctness is proven.


def gpu_score(gpu: dict | None) -> float:
    if not gpu:
        return 0.0
    vram = gpu.get("vram_mb") or 0
    return min(vram / 24576.0, 1.0)  # normalize at 24GB class


def cpu_score(cpu: dict | None) -> float:
    cores = (cpu or {}).get("physical_cores") or (cpu or {}).get("logical_cores") or 0
    return min(cores / 16.0, 1.0)


def ram_score(ram: dict | None) -> float:
    total_mb = (ram or {}).get("total_mb") or 0
    return min(total_mb / 65536.0, 1.0)  # normalize at 64GB


def capability_scores(profile: dict | None) -> dict:
    if not profile:
        return {}
    gpus = profile.get("gpus") or []
    return {
        "gpu": max((gpu_score(g) for g in gpus), default=0.0),
        "cpu": cpu_score(profile.get("cpu")),
        "ram": ram_score(profile.get("ram")),
    }
