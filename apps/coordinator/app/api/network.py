"""Network + worker-activity endpoints for the dashboard (Sprint 16; Sprint 26: capacity)."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models.attempt import WorkUnitAttempt
from app.models.capability import WorkerCapability
from app.models.job import Job
from app.models.result import Result
from app.models.work_unit import LEASE_STATES, WorkUnit
from app.models.worker import Worker
from app.schemas.job import WorkUnitOut
from app.services.availability import effective_status
from app.services.tiers import hardware_tiers

router = APIRouter()


@router.get("/network/summary")
def network_summary(db: Session = Depends(get_db)) -> dict:
    """Fleet-wide rollup: workers, units, jobs, recent throughput."""
    timeout = get_settings().heartbeat_timeout_seconds
    workers = db.query(Worker).all()
    by_status: dict[str, int] = {}
    for w in workers:
        status = effective_status(w, timeout)
        by_status[status] = by_status.get(status, 0) + 1

    units = db.query(WorkUnit.status, func.count(WorkUnit.id)).group_by(WorkUnit.status).all()
    units_by_status = {status: count for status, count in units}
    jobs_total = db.query(func.count(Job.id)).scalar() or 0

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent = 0
    for (created_at,) in db.query(Result.created_at).all():
        if created_at is None:
            continue
        ts = created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else created_at
        if ts >= cutoff:
            recent += 1

    return {
        "workers": {"total": len(workers), "by_status": by_status},
        "units": units_by_status,
        "jobs": jobs_total,
        "completed_last_5m": recent,
    }


@router.get("/network/capacity")
def network_capacity(db: Session = Depends(get_db)) -> dict:
    """Fleet capacity rollup for the beta dashboard (Sprint 26).

    Sums what the pool can offer right now: online workers only contribute
    their cores/RAM/GPUs; versions flag outdated workers for updates.
    """
    timeout = get_settings().heartbeat_timeout_seconds
    workers = db.query(Worker).all()
    online = [w for w in workers if effective_status(w, timeout) == "online"]

    versions: dict[str, int] = {}
    for w in workers:
        versions[w.worker_version or "unknown"] = versions.get(w.worker_version or "unknown", 0) + 1

    cores = ram_mb = 0
    gpus_by_tier: dict[str, int] = {}
    gpus_by_vendor: dict[str, int] = {}
    cached: dict[str, int] = {}
    runtimes: dict[str, int] = {}
    for w in online:
        cap = db.get(WorkerCapability, w.id)
        profile = cap.profile if cap and isinstance(cap.profile, dict) else {}
        cpu = profile.get("cpu") or {}
        cores += cpu.get("physical_cores") or cpu.get("logical_cores") or 0
        ram_mb += (profile.get("ram") or {}).get("total_mb") or 0
        for gpu in profile.get("gpus") or []:
            tiers = hardware_tiers({**profile, "gpus": [gpu]})
            tier = tiers.get("gpu") or "unknown"
            gpus_by_tier[tier] = gpus_by_tier.get(tier, 0) + 1
            vendor = str(gpu.get("vendor", "unknown"))
            gpus_by_vendor[vendor] = gpus_by_vendor.get(vendor, 0) + 1
        for model in profile.get("cached_models") or []:
            key = f"{model.get('name')}@{model.get('version')}"
            cached[key] = cached.get(key, 0) + 1
        for runtime in profile.get("runtimes") or []:
            runtimes[runtime] = runtimes.get(runtime, 0) + 1

    units = db.query(WorkUnit.status, func.count(WorkUnit.id)).group_by(WorkUnit.status).all()
    return {
        "online_workers": len(online),
        "total_workers": len(workers),
        "cpu_cores": cores,
        "ram_mb": ram_mb,
        "gpus_by_tier": gpus_by_tier,
        "gpus_by_vendor": gpus_by_vendor,
        "cached_models": cached,
        "runtimes": runtimes,
        "versions": versions,
        "queued_units": dict(units).get("queued", 0),
    }


@router.get("/workers/{worker_id}/work", response_model=list[WorkUnitOut])
def worker_current_work(worker_id: str, db: Session = Depends(get_db)) -> list[WorkUnitOut]:
    """Units currently leased to this worker (dispatched/running)."""
    if db.get(Worker, worker_id) is None:
        raise HTTPException(status_code=404, detail={"error": "unknown worker"})
    rows = (
        db.query(WorkUnit)
        .filter(WorkUnit.assigned_worker_id == worker_id,
                WorkUnit.status.in_(LEASE_STATES))
        .order_by(WorkUnit.dispatched_at)
        .all()
    )
    return [WorkUnitOut.model_validate(r) for r in rows]


@router.get("/workers/{worker_id}/stats")
def worker_contribution_stats(worker_id: str, db: Session = Depends(get_db)) -> dict:
    """Contribution totals: completed/failed units + summed execution time."""
    if db.get(Worker, worker_id) is None:
        raise HTTPException(status_code=404, detail={"error": "unknown worker"})
    completed = (
        db.query(func.count(Result.work_unit_id))
        .filter(Result.worker_id == worker_id, Result.ok.is_(True))
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(Result.work_unit_id))
        .filter(Result.worker_id == worker_id, Result.ok.is_(False))
        .scalar()
        or 0
    )
    total_ms = (
        db.query(func.coalesce(func.sum(Result.execution_ms), 0.0))
        .filter(Result.worker_id == worker_id, Result.ok.is_(True))
        .scalar()
        or 0.0
    )
    attempts = (
        db.query(func.count(WorkUnitAttempt.id))
        .filter(WorkUnitAttempt.worker_id == worker_id)
        .scalar()
        or 0
    )
    return {
        "worker_id": worker_id,
        "completed_units": completed,
        "failed_units": failed,
        "total_execution_ms": round(float(total_ms), 3),
        "attempts": attempts,
    }
