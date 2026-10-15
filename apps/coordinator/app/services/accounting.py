"""Compute accounting (Sprint 27): estimates, availability, summaries.

Estimation model v1 (stated plainly, not hidden):
- `cpu_time_ms = execution_ms`: our deterministic workloads are
  single-threaded and compute-bound, so wall time ≈ one saturated core.
- `gpu_time_ms = execution_ms` iff the job's requirements asked for a GPU,
  else 0. We do not (yet) measure per-unit device utilization.

Availability: fraction of the lookback window the worker was *covered* by
fresh heartbeats. Any gap longer than 2× the heartbeat timeout counts as
offline. No heartbeats at all → availability None (unknown, not zero).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.accounting import ContributionRecord
from app.models.heartbeat import WorkerHeartbeat


def estimate_times(execution_ms: float | None, requires_gpu: bool) -> tuple[float | None, float | None]:
    """(cpu_time_ms, gpu_time_ms) under the v1 model. None propagates."""
    if execution_ms is None:
        return None, None
    cpu_time_ms = float(execution_ms)
    gpu_time_ms = float(execution_ms) if requires_gpu else 0.0
    return cpu_time_ms, gpu_time_ms


def record_completion(
    db: Session,
    *,
    work_unit_id: str,
    job_id: str,
    worker_id: str,
    workload_type: str,
    execution_ms: float | None,
    requires_gpu: bool,
    verified_by: str | None = None,
) -> ContributionRecord:
    """Write-once contribution record. Re-calling for the same unit is a no-op."""
    existing = db.query(ContributionRecord).filter_by(work_unit_id=work_unit_id).first()
    if existing is not None:
        return existing
    cpu_time_ms, gpu_time_ms = estimate_times(execution_ms, requires_gpu)
    row = ContributionRecord(
        work_unit_id=work_unit_id,
        job_id=job_id,
        worker_id=worker_id,
        workload_type=workload_type,
        execution_ms=execution_ms,
        cpu_time_ms=cpu_time_ms,
        gpu_time_ms=gpu_time_ms,
        verified=True,
        verified_by=verified_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def void_record(db: Session, work_unit_id: str) -> bool:
    """Mark a record void on verification overturn. True when a row existed."""
    row = db.query(ContributionRecord).filter_by(work_unit_id=work_unit_id).first()
    if row is None:
        return False
    row.verified = False
    row.voided_at = datetime.now(timezone.utc)
    db.commit()
    return True


def availability_fraction(db: Session, worker_id: str, hours: float = 24.0) -> float | None:
    """Share of the lookback window covered by fresh heartbeats (None if none)."""
    timeout = get_settings().heartbeat_timeout_seconds
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    stamps = [
        _aware(r[0])
        for r in db.query(WorkerHeartbeat.received_at)
        .filter(WorkerHeartbeat.worker_id == worker_id,
                WorkerHeartbeat.received_at >= cutoff.replace(tzinfo=None))
        .order_by(WorkerHeartbeat.received_at)
        .all()
        if r[0] is not None
    ]
    if not stamps:
        return None
    now = datetime.now(timezone.utc)
    covered = timedelta(0)
    cursor = max(stamps[0], cutoff)
    for stamp in stamps:
        if (stamp - cursor) <= timedelta(seconds=2 * timeout):
            covered += stamp - cursor
        cursor = stamp
    if (now - cursor) <= timedelta(seconds=2 * timeout):
        covered += now - cursor
    total = (now - cutoff).total_seconds()
    return round(min(covered.total_seconds() / total, 1.0), 4) if total > 0 else None


def worker_summary(db: Session, worker_id: str) -> dict:
    """Per-worker accounting rollup + availability + reliability link."""
    from app.models.worker import Worker
    from app.services import reputation

    if db.get(Worker, worker_id) is None:
        raise KeyError("unknown worker")
    rows = db.query(ContributionRecord).filter_by(worker_id=worker_id).all()
    valid = [r for r in rows if r.verified]
    return {
        "worker_id": worker_id,
        "units_completed": len(rows),
        "units_valid": len(valid),
        "units_voided": len(rows) - len(valid),
        "total_execution_ms": round(sum(r.execution_ms or 0.0 for r in rows), 3),
        "total_cpu_time_ms": round(sum(r.cpu_time_ms or 0.0 for r in valid), 3),
        "total_gpu_time_ms": round(sum(r.gpu_time_ms or 0.0 for r in valid), 3),
        "verified_units": sum(1 for r in valid if r.verified_by or r.verified),
        "availability_24h": availability_fraction(db, worker_id),
        "reliability": reputation.reliability(db, worker_id)["score"],
    }


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
