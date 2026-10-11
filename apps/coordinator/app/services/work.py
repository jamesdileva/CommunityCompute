"""Work assignment + result handling (Sprint 6).

FIFO claim, deterministic verification (coordinator recomputes the expected
result), and job aggregation. Leases/expiry arrive in Sprint 7 — this sprint
claims optimistically: a claimed unit is `dispatched`; only a verified result
moves it to `completed`, and a wrong/absent result moves it to `failed`
(never silently accepted).
"""

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.protocol import PROTOCOL_VERSION

from app.models.job import Job
from app.models.result import Result
from app.models.work_unit import WorkUnit
from app.schemas.work import WorkAssignment, WorkResult
from app.services.workloads.hello_compute import compute as hello_compute, output_hash

log = logging.getLogger("coordinator")

DEFAULT_WORKLOAD_TYPE = "hello_compute"


def claim_next_unit(db: Session, worker_id: str) -> WorkAssignment | None:
    """FIFO: oldest queued unit overall → dispatched to this worker. None when idle."""
    unit = (
        db.query(WorkUnit)
        .filter_by(status="queued")
        .order_by(WorkUnit.created_at, WorkUnit.sequence)
        .first()
    )
    if unit is None:
        return None
    job = db.get(Job, unit.job_id)
    unit.status = "dispatched"
    unit.assigned_worker_id = worker_id
    unit.dispatched_at = datetime.now(timezone.utc)
    if job is not None and job.status == "queued":
        job.status = "running"
    db.commit()
    db.refresh(unit)
    log.info("unit %s (job %s) dispatched to %s", unit.id, unit.job_id, worker_id)
    return WorkAssignment(
        protocol_version=PROTOCOL_VERSION,
        work_unit_id=unit.id,
        job_id=unit.job_id,
        workload_type=job.workload_type if job else DEFAULT_WORKLOAD_TYPE,
        range_start=unit.range_start,
        range_end=unit.range_end,
        params=dict(job.params) if job and isinstance(job.params, dict) else {},
    )


def submit_result(db: Session, work_unit_id: str, payload: WorkResult) -> tuple[bool, str | None, Result]:
    """Verify + persist. Returns (accepted, rejection_reason, result_row).

    - Unknown unit → KeyError (caller maps to 404).
    - Verified value (+ hash) → unit completed; resubmitting a completed unit
      with the same verdict is idempotent.
    - Mismatch → unit failed, result recorded with ok=False + reason.
    """
    unit = db.get(WorkUnit, work_unit_id)
    if unit is None:
        raise KeyError("unknown work unit")
    job = db.get(Job, unit.job_id)

    existing = db.get(Result, work_unit_id)
    if existing is not None and unit.status == "completed":
        return True, None, existing  # idempotent duplicate

    op = (job.params or {}).get("op", "sum") if job else "sum"
    ok = False
    error = payload.error
    if payload.status == "completed":
        try:
            expected = hello_compute(op, unit.range_start, unit.range_end)
            if payload.value != expected:
                error = f"value mismatch: expected {expected!r}, got {payload.value!r}"
            else:
                ok = True
        except ValueError as exc:
            error = str(exc)
        if ok and payload.output_hash is not None:
            if payload.output_hash != output_hash(op, payload.value):
                ok = False
                error = "output hash mismatch (corrupted result)"
    else:
        error = payload.error or "worker reported failure"

    execution_ms = _as_float(payload.metrics.get("execution_ms"))
    result = existing or Result(work_unit_id=work_unit_id)
    result.worker_id = payload.worker_id
    result.ok = ok
    result.value = payload.value
    result.output_hash = payload.output_hash
    result.execution_ms = execution_ms
    result.error = None if ok else error
    if existing is None:
        db.add(result)

    unit.status = "completed" if ok else "failed"
    db.commit()
    db.refresh(result)
    if ok:
        log.info("unit %s completed by %s (%sms)", work_unit_id, payload.worker_id, execution_ms)
    else:
        log.info("unit %s REJECTED from %s: %s", work_unit_id, payload.worker_id, error)
    _refresh_job_status(db, unit.job_id)
    return ok, (None if ok else (error or "rejected")), result


def aggregate_job(db: Session, job_id: str) -> dict | None:
    """Per-status counts + final aggregate once every unit completed."""
    job = db.get(Job, job_id)
    if job is None:
        return None
    units = sorted(db.query(WorkUnit).filter_by(job_id=job_id).all(), key=lambda u: u.sequence)
    counts: dict[str, int] = {}
    for u in units:
        counts[u.status] = counts.get(u.status, 0) + 1
    out: dict = {"counts": counts}
    if units and counts.get("completed", 0) == len(units):
        op = (job.params or {}).get("op", "sum")
        if op == "sum":
            total = 0
            for u in units:
                r = db.get(Result, u.id)
                if r and isinstance(r.value, (int, float)):
                    total += r.value
            out["final"] = total
        elif op == "hash":
            h = hashlib.sha256()
            for u in units:
                r = db.get(Result, u.id)
                h.update(str(r.value if r else "").encode())
            out["final"] = h.hexdigest()
    return out


def _refresh_job_status(db: Session, job_id: str) -> None:
    """Roll unit states up into the job: failed > completed > running > queued."""
    job = db.get(Job, job_id)
    if job is None:
        return
    units = list(db.query(WorkUnit).filter_by(job_id=job_id).all())
    counts: dict[str, int] = {}
    for u in units:
        counts[u.status] = counts.get(u.status, 0) + 1
    if counts.get("failed"):
        job.status = "failed"
    elif units and counts.get("completed", 0) == len(units):
        job.status = "completed"
    elif counts.get("completed") or counts.get("dispatched") or counts.get("running"):
        job.status = "running"
    else:
        job.status = "queued"
    db.commit()


def _as_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None
