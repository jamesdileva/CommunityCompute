"""Scheduling score (Sprint 31, architecture §10).

FIFO picks the oldest compatible unit; this module ranks *compatible*
candidates so the worker pulls the unit that best fits it. The score is a
weighted sum of the architecture §10 inputs, each normalized to a small,
comparable range and reported separately so it can be inspected (explain):

    score =  w_fit   * capability_fit        # headroom on the axes the job needs
           + w_speed * estimated_speed       # 1/(1+historical_ms/ref) for this worker
           + w_cache * cached_model          # 1 when the job's model is already local
           + w_rel   * reliability           # reputation (unrated -> neutral 0.5)
           + w_avail * availability          # idle load x lease headroom
           - w_xfer  * transfer_cost         # payload + uncached model bytes, normalized
           - w_loc   * location_penalty      # job.location vs worker.location (0 when unset)

FIFO (`created_at, sequence`) is the tie-break, so equal scores degrade to the
Sprint-9 behaviour exactly. Every component is coordinator-derived: no worker
protocol change (the `location` term stays neutral until a worker ever
reports one). Hard compatibility (compat.check) still gates first — scoring
never lets an incompatible worker through, it only orders eligible ones.

Design notes:
- In the pull model, worker-level terms (speed/reliability/availability) are
  constant across one worker's candidates, so the *per-unit* discriminators
  are capability_fit, cached_model, and transfer_cost. The worker-level terms
  still matter when comparing workers (Sprint 32 simulation, and the
  `score` breakdown exposed for operators).
- `Do not over-engineer scoring during the two-node prototype` (architecture
  §10): weights are settings, defaults are deliberately simple, and the model
  is pure + unit-tested rather than clever.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings

# Positive contributions (higher is better) and negative ones (subtracted).
POSITIVE = ("capability_fit", "estimated_speed", "cached_model",
            "reliability", "availability")
NEGATIVE = ("transfer_cost", "location_penalty")

DEFAULT_REFERENCE_MS = 50.0
DEFAULT_REFERENCE_TRANSFER_BYTES = 50_000_000  # 50 MB
DEFAULT_MODEL_MB = 256
DEFAULT_BYTES_PER_RANGE_UNIT = 4


def weights(settings=None) -> dict:
    """Component weights from settings (see config.py SCORING_*)."""
    s = settings or get_settings()
    return {
        "capability_fit": s.scoring_weight_capability,
        "estimated_speed": s.scoring_weight_speed,
        "cached_model": s.scoring_weight_cache,
        "reliability": s.scoring_weight_reliability,
        "availability": s.scoring_weight_availability,
        "transfer_cost": s.scoring_weight_transfer,
        "location_penalty": s.scoring_weight_location,
    }


# --- component functions (pure, individually testable) ------------------------


def capability_fit(requirements: dict | None, profile: dict | None,
                   settings=None) -> float:
    """Mean capability score on the axes the job cares about (0..1).

    A job with no capability requirements averages whatever the worker
    reports, so more capable workers score higher; a job that needs a GPU is
    judged on GPU headroom alone.
    """
    from app.services.tiers import capability_scores

    scores = capability_scores(profile)
    reqs = requirements or {}
    axes: list[str] = []
    if reqs.get("gpu"):
        axes.append("gpu")
    if reqs.get("cpu_cores") is not None:
        axes.append("cpu")
    if reqs.get("ram_mb") is not None:
        axes.append("ram")
    if not axes:
        axes = [a for a in ("gpu", "cpu", "ram") if a in scores]
    values = [scores.get(a, 0.0) for a in axes]
    return round(sum(values) / len(values), 6) if values else 0.0


def estimated_speed(mean_execution_ms: float | None, settings=None) -> float:
    """Map a worker's historical mean execution time to 0..1 (None -> 0.5)."""
    s = settings or get_settings()
    reference = s.scoring_reference_ms or DEFAULT_REFERENCE_MS
    if mean_execution_ms is None:
        return 0.5  # unmeasured -> neutral, never punished
    ms = max(float(mean_execution_ms), 0.0)
    return round(reference / (reference + ms), 6)


def cached_model(requirements: dict | None, cached_models: set[str]) -> float:
    """1.0 when the job's model is already local, else 0.0 (no model -> 0.0)."""
    model = (requirements or {}).get("model")
    if not model:
        return 0.0
    return 1.0 if model in cached_models else 0.0


def reliability(reliability_score: float | None) -> float:
    """Reputation score passed through; unrated -> neutral 0.5."""
    return 0.5 if reliability_score is None else round(float(reliability_score), 6)


def availability(cpu_percent: float | None, gpu_percent: float | None,
                 active_leases: int, max_leases: int) -> float:
    """Idle-load factor x lease headroom (0..1). Unknown load -> neutral 0.5."""
    loads = [p for p in (cpu_percent, gpu_percent) if p is not None]
    load_factor = 0.5 if not loads else max(0.0, 1.0 - max(loads) / 100.0)
    cap = max(int(max_leases), 1)
    lease_factor = max(0.0, 1.0 - int(active_leases) / cap)
    return round(load_factor * lease_factor, 6)


def transfer_cost(range_start: int, range_end: int, requirements: dict | None,
                  cached_models: set[str], settings=None) -> float:
    """Normalized bytes to move (0..1): payload + an uncached model download."""
    s = settings or get_settings()
    reference = s.scoring_reference_transfer_bytes or DEFAULT_REFERENCE_TRANSFER_BYTES
    per_unit = s.scoring_bytes_per_range_unit or DEFAULT_BYTES_PER_RANGE_UNIT
    span = max(0, int(range_end) - int(range_start) + 1)
    payload = span * per_unit
    model = (requirements or {}).get("model")
    model_bytes = 0
    if model and model not in cached_models:
        model_mb = int((requirements or {}).get("model_mb") or s.scoring_model_default_mb
                       or DEFAULT_MODEL_MB)
        model_bytes = model_mb * 1024 * 1024
    return round(min((payload + model_bytes) / reference, 1.0), 6)


def location_penalty(requirements: dict | None, profile: dict | None) -> float:
    """0 when either side is silent or locations match; 1.0 on a mismatch.

    Coordinator-derived only (Sprint 31): workers do not report a location
    yet, so this stays 0 in practice and lights up if/when they do.
    """
    want = (requirements or {}).get("location")
    have = (profile or {}).get("location") if profile else None
    if not want or not have:
        return 0.0
    return 0.0 if str(want).lower() == str(have).lower() else 1.0


# --- aggregate + explanation --------------------------------------------------


def score(
    *,
    requirements: dict | None,
    range_start: int,
    range_end: int,
    profile: dict | None,
    cached_models: set[str] | None = None,
    reliability_score: float | None = None,
    mean_execution_ms: float | None = None,
    cpu_percent: float | None = None,
    gpu_percent: float | None = None,
    active_leases: int = 0,
    max_leases: int = 1,
    settings=None,
) -> dict:
    """Full breakdown for one (worker, unit) pair: components, weights, total."""
    s = settings or get_settings()
    cached = cached_models or set()
    components = {
        "capability_fit": capability_fit(requirements, profile, s),
        "estimated_speed": estimated_speed(mean_execution_ms, s),
        "cached_model": cached_model(requirements, cached),
        "reliability": reliability(reliability_score),
        "availability": availability(cpu_percent, gpu_percent, active_leases,
                                     max_leases),
        "transfer_cost": transfer_cost(range_start, range_end, requirements,
                                       cached, s),
        "location_penalty": location_penalty(requirements, profile),
    }
    w = weights(s)
    contributions = {name: round(w[name] * components[name], 6)
                     for name in components}
    total = round(
        sum(contributions[n] for n in POSITIVE)
        - sum(contributions[n] for n in NEGATIVE),
        6,
    )
    return {"total": total, "components": components, "weights": w,
            "contributions": contributions}


# --- DB-backed helper (used by claim + explain) -------------------------------


def worker_context(db: Session, worker_id: str, settings=None) -> dict:
    """Gather the worker-level inputs once per claim (profile, rep, speed, load)."""
    from app.models.accounting import ContributionRecord
    from app.models.capability import WorkerCapability
    from app.models.work_unit import LEASE_STATES, WorkUnit
    from app.models.worker import Worker
    from app.services import reputation

    s = settings or get_settings()
    worker = db.get(Worker, worker_id)
    cap = db.get(WorkerCapability, worker_id)
    profile = dict(cap.profile) if cap and isinstance(cap.profile, dict) else None
    mean_ms = (
        db.query(func.avg(ContributionRecord.execution_ms))
        .filter(ContributionRecord.worker_id == worker_id,
                ContributionRecord.verified.is_(True))
        .scalar()
    )
    rel_score = None
    if worker is not None:
        try:
            rel_score = reputation.reliability(db, worker_id)["score"]
        except KeyError:
            rel_score = None
    active = (
        db.query(WorkUnit)
        .filter(WorkUnit.assigned_worker_id == worker_id,
                WorkUnit.status.in_(LEASE_STATES))
        .count()
    )
    cached: set[str] = set()
    if profile:
        for entry in profile.get("cached_models") or []:
            if isinstance(entry, dict) and entry.get("name"):
                cached.add(entry["name"])
    return {
        "profile": profile,
        "reliability": rel_score,
        "mean_execution_ms": (float(mean_ms) if mean_ms is not None else None),
        "cpu_percent": worker.cpu_percent if worker else None,
        "gpu_percent": worker.gpu_percent if worker else None,
        "active_leases": active,
        "max_leases": s.max_leases_per_worker,
        "reported_cached_models": cached,
    }


def score_with_context(context: dict, *, requirements: dict | None,
                       range_start: int, range_end: int,
                       cached_models: set[str] | None = None,
                       settings=None) -> dict:
    """Score one candidate using a pre-gathered worker context (one query/call)."""
    cached = (context.get("reported_cached_models") or set()) | (cached_models or set())
    return score(
        requirements=requirements,
        range_start=range_start,
        range_end=range_end,
        profile=context.get("profile"),
        cached_models=cached,
        reliability_score=context.get("reliability"),
        mean_execution_ms=context.get("mean_execution_ms"),
        cpu_percent=context.get("cpu_percent"),
        gpu_percent=context.get("gpu_percent"),
        active_leases=context.get("active_leases", 0),
        max_leases=context.get("max_leases", 1),
        settings=settings,
    )


def rank(entries: list[tuple]) -> list[tuple]:
    """Sort scoring entries best-first with a stable FIFO tie-break.

    Each entry is ``(total, created_at, sequence, payload)``; equal totals fall
    back to ``(created_at, sequence)`` — i.e. plain FIFO, exactly as before.
    """
    return sorted(entries, key=lambda e: (-e[0], _aware(e[1]), e[2]))


def _aware(value):
    from datetime import timezone

    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
