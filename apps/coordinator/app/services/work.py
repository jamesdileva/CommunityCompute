"""Work assignment + result handling (Sprint 6; Sprint 7: leases + attempts).

Leasing model (implementation-guide §14): a claimed unit holds a lease
(`lease_id, worker, started_at, expires_at, attempt_number`). When a lease
expires the unit returns to the queue and any other worker may retry it —
this is what makes worker disappearance survivable. Sweeping happens lazily
on claim (prototype: no background reaper).
"""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.protocol import PROTOCOL_VERSION

from app.config import get_settings
from app.models.attempt import WorkUnitAttempt
from app.models.job import Job
from app.models.result import Result
from app.models.work_unit import LEASE_STATES, WorkUnit
from app.schemas.work import WorkAssignment, WorkResult
from app.services.workloads.hello_compute import compute as hello_compute, output_hash

log = logging.getLogger("coordinator")

DEFAULT_WORKLOAD_TYPE = "hello_compute"


def claim_next_unit(db: Session, worker_id: str) -> WorkAssignment | None:
    """Expire stale leases (lazy sweep), then FIFO-claim the oldest queued unit."""
    _sweep_expired_leases(db)
    unit = (
        db.query(WorkUnit)
        .filter_by(status="queued")
        .order_by(WorkUnit.created_at, WorkUnit.sequence)
        .first()
    )
    if unit is None:
        return None
    job = db.get(Job, unit.job_id)
    now = datetime.now(timezone.utc)
    lease_seconds = get_settings().lease_duration_seconds
    attempt_number = (
        db.query(WorkUnitAttempt).filter_by(work_unit_id=unit.id).count() + 1
    )
    lease_id = str(uuid.uuid4())
    unit.status = "dispatched"
    unit.assigned_worker_id = worker_id
    unit.dispatched_at = now
    unit.lease_id = lease_id
    unit.lease_worker_id = worker_id
    unit.lease_started_at = now
    unit.lease_expires_at = now + timedelta(seconds=lease_seconds)
    unit.attempt_number = attempt_number
    db.add(
        WorkUnitAttempt(
            work_unit_id=unit.id,
            attempt_number=attempt_number,
            worker_id=worker_id,
            lease_id=lease_id,
            started_at=now,
        )
    )
    if job is not None and job.status == "queued":
        job.status = "running"
    db.commit()
    db.refresh(unit)
    log.info(
        "unit %s leased to %s (attempt %d, expires %s)",
        unit.id, worker_id, attempt_number, unit.lease_expires_at,
    )
    return WorkAssignment(
        protocol_version=PROTOCOL_VERSION,
        work_unit_id=unit.id,
        job_id=unit.job_id,
        workload_type=job.workload_type if job else DEFAULT_WORKLOAD_TYPE,
        range_start=unit.range_start,
        range_end=unit.range_end,
        params=dict(job.params) if job and isinstance(job.params, dict) else {},
        lease_id=lease_id,
        lease_expires_at=unit.lease_expires_at,
        attempt_number=attempt_number,
    )


def _sweep_expired_leases(db: Session) -> int:
    """Requeue units whose lease expired. Returns count requeued."""
    now = datetime.now(timezone.utc)
    stale = (
        db.query(WorkUnit)
        .filter(WorkUnit.status.in_(LEASE_STATES), WorkUnit.lease_expires_at.isnot(None))
        .all()
    )
    requeued = 0
    for unit in stale:
        expires = unit.lease_expires_at
        expires = expires.replace(tzinfo=timezone.utc) if expires.tzinfo is None else expires
        if expires > now:
            continue
        attempt = (
            db.query(WorkUnitAttempt)
            .filter_by(work_unit_id=unit.id, lease_id=unit.lease_id)
            .first()
        )
        if attempt is not None and attempt.outcome is None:
            attempt.ended_at = now
            attempt.outcome = "expired"
        unit.status = "queued"
        unit.lease_id = None
        unit.lease_worker_id = None
        unit.lease_expires_at = None
        unit.assigned_worker_id = None
        requeued += 1
        log.info("unit %s lease expired -> requeued (worker %s vanished)", unit.id,
                 unit.lease_worker_id or attempt.worker_id if attempt else "?")
    if requeued:
        db.commit()
    return requeued


def submit_result(db: Session, work_unit_id: str, payload: WorkResult) -> tuple[bool, str | None, Result]:
    """Verify + persist. Returns (accepted, rejection_reason, result_row).

    409 territory: a unit already verified-completed only accepts an
    identical resubmission (idempotent 200); any different result conflicts.
    """
    unit = db.get(WorkUnit, work_unit_id)
    if unit is None:
        raise KeyError("unknown work unit")
    job = db.get(Job, unit.job_id)

    existing = db.get(Result, work_unit_id)
    if unit.status == "completed":
        if (
            existing is not None
            and existing.ok
            and payload.status == "completed"
            and payload.value == existing.value
        ):
            return True, None, existing  # idempotent duplicate of the verified result
        raise Conflict("work unit already completed by another worker")

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
    unit.lease_id = None
    unit.lease_worker_id = None
    unit.lease_expires_at = None
    db.commit()
    db.refresh(result)

    # close the open attempt for this lease/worker
    attempt = (
        db.query(WorkUnitAttempt)
        .filter_by(work_unit_id=work_unit_id, worker_id=payload.worker_id, outcome=None)
        .order_by(WorkUnitAttempt.started_at.desc())
        .first()
    )
    if attempt is not None:
        attempt.ended_at = datetime.now(timezone.utc)
        attempt.outcome = "completed" if ok else "failed"
        db.commit()

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


class Conflict(Exception):
    """Late/duplicate result for an already-completed unit (maps to HTTP 409)."""
