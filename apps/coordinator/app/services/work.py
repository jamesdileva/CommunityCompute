"""Work assignment + result handling (Sprint 6; S7 leases; S8 classified verification).

Leasing model (implementation-guide §14): a claimed unit holds a lease
(`lease_id, worker, started_at, expires_at, attempt_number`). When a lease
expires the unit returns to the queue and any other worker may retry it —
this is what makes worker disappearance survivable. Sweeping happens lazily
on claim (prototype: no background reaper).

Verification model (Sprint 8): every result is classified — accepted, or
rejected with a `failure_kind` (value_mismatch, hash_mismatch, worker_error,
unsupported_workload, verification_disagreement). Jobs created with
`verify_sample > 0` spawn duplicate check units claimed by a *different*
worker; agreement confirms the original (`verified_by`), disagreement fails
both (verification overturn).
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
from app.models.worker import Worker
from app.schemas.work import WorkAssignment, WorkResult
from app.services import reputation
from app.services.compat import check
from app.services.workloads import expected as workload_expected
from app.services.workloads import output_hash as workload_output_hash

log = logging.getLogger("coordinator")

DEFAULT_WORKLOAD_TYPE = "hello_compute"

# Failure classification (Sprint 8).
VALUE_MISMATCH = "value_mismatch"
HASH_MISMATCH = "hash_mismatch"
WORKER_ERROR = "worker_error"
UNSUPPORTED_WORKLOAD = "unsupported_workload"
VERIFICATION_DISAGREEMENT = "verification_disagreement"


def claim_next_unit(db: Session, worker_id: str,
                    cached_models: set[str] | None = None) -> WorkAssignment | None:
    """Expire stale leases (lazy sweep), then claim the best queued unit.

    Ordering (Sprint 15): model-cached units first (stable FIFO within each
    group), then everything else — cache affinity is a preference, so
    uncached workers are still served plain units.
    Also enforces: duplicates skip the original's worker; the worker's
    stored capability profile must satisfy the job's requirements (S9).
    """
    _sweep_expired_leases(db)
    worker = db.get(Worker, worker_id)
    if worker is not None and worker.paused_by_operator:
        log.debug("unit claim refused for operator-paused %s", worker_id)
        return None  # enforcement, not display: paused workers get nothing
    candidates = (
        db.query(WorkUnit)
        .filter_by(status="queued")
        .order_by(WorkUnit.created_at, WorkUnit.sequence)
        .all()
    )
    profile = _worker_profile(db, worker_id)
    cached = cached_models or set()
    fallback: WorkUnit | None = None
    for candidate in candidates:
        if candidate.verify_of is not None and _original_worker(db, candidate) == worker_id:
            continue  # verification must come from a different worker
        job = db.get(Job, candidate.job_id)
        reqs = (job.requirements or {}) if job else {}
        model_req = reqs.get("model")
        if model_req and model_req in cached:
            if _compatible(reqs, profile, candidate.id, worker_id):
                unit = candidate
                break
            continue
        if fallback is None and _compatible(reqs, profile, candidate.id, worker_id):
            fallback = candidate
    else:
        unit = fallback
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
        manifest_signature=_sign_assignment(
            unit.id, unit.job_id,
            job.workload_type if job else DEFAULT_WORKLOAD_TYPE,
            unit.range_start, unit.range_end,
            dict(job.params) if job and isinstance(job.params, dict) else {},
        ),
    )


def _sign_assignment(work_unit_id: str, job_id: str, workload_type: str,
                     range_start: int, range_end: int, params: dict) -> str:
    """Seal the claim (Sprint 21). The worker verifies before executing."""
    from packages.protocol.signing import sign_manifest

    return sign_manifest(
        {
            "work_unit_id": work_unit_id,
            "job_id": job_id,
            "workload_type": workload_type,
            "range_start": range_start,
            "range_end": range_end,
            "params": params,
        },
        get_settings().workload_signing_key,
    )


def _compatible(reqs: dict, profile: dict | None, unit_id: str, worker_id: str) -> bool:
    compatible, reason = check(reqs, profile)
    if not compatible:
        log.debug("unit %s skipped for %s: %s", unit_id, worker_id, reason)
    return compatible


def _original_worker(db: Session, duplicate: WorkUnit) -> str | None:
    """Worker id behind the original unit of a duplicate (None when unknown)."""
    if not duplicate.verify_of:
        return None
    original_result = db.get(Result, duplicate.verify_of)
    return original_result.worker_id if original_result else None


def _worker_profile(db: Session, worker_id: str) -> dict | None:
    """Latest stored capability profile (None when the worker never reported)."""
    from app.models.capability import WorkerCapability

    cap = db.get(WorkerCapability, worker_id)
    return dict(cap.profile) if cap and isinstance(cap.profile, dict) else None


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
            # Sprint 23: the vanished worker earns an expiry mark (fault signal).
            reputation.record(db, attempt.worker_id, reputation.LEASE_EXPIRED,
                              work_unit_id=unit.id)
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
    """Classify + persist. Returns (accepted, rejection_reason, result_row).

    - Unknown unit → KeyError (caller maps to 404).
    - Already verified-completed: identical resubmission → idempotent 200,
      anything else → Conflict (409).
    - Completing an original on a sampled job spawns a duplicate check unit
      for a *different* worker; completing a duplicate compares against the
      original (match → `verified_by`, mismatch → disagreement, both failed).
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

    workload_type = job.workload_type if job else DEFAULT_WORKLOAD_TYPE
    op = (job.params or {}).get("op", "sum") if job else "sum"
    original_value = None
    if unit.verify_of is not None:
        # Duplicate check: the question is reproduction of the confirmed
        # original, not re-derivation of the expectation.
        original_result = db.get(Result, unit.verify_of)
        original_value = original_result.value if original_result else None
    ok, kind, error = _classify(payload, unit, workload_type, op, original_value,
                                job_params=(job.params or {}) if job else {})

    execution_ms = _as_float(payload.metrics.get("execution_ms"))
    result = existing or Result(work_unit_id=work_unit_id)
    result.worker_id = payload.worker_id
    result.ok = ok
    result.value = payload.value
    result.output_hash = payload.output_hash
    result.execution_ms = execution_ms
    result.metrics = dict(payload.metrics) if isinstance(payload.metrics, dict) else None
    result.error = None if ok else error
    result.failure_kind = None if ok else kind
    if existing is None:
        db.add(result)

    unit.status = "completed" if ok else "failed"
    unit.lease_id = None
    unit.lease_worker_id = None
    unit.lease_expires_at = None
    db.commit()
    db.refresh(result)
    _close_attempt(db, work_unit_id, payload.worker_id, ok)

    if ok:
        log.info("unit %s completed by %s (%sms)", work_unit_id, payload.worker_id, execution_ms)
        reputation.record(db, payload.worker_id, reputation.RESULT_ACCEPTED,
                          work_unit_id=work_unit_id)
        if unit.verify_of is None:
            _maybe_spawn_duplicate(db, job, unit)
        else:
            _confirm_original(db, unit, result)
    else:
        log.info("unit %s REJECTED from %s [%s]: %s",
                 work_unit_id, payload.worker_id, kind, error)
        reputation.record(db, payload.worker_id, reputation.RESULT_REJECTED,
                          failure_kind=kind, work_unit_id=work_unit_id,
                          detail=error)
        if unit.verify_of is not None and kind == VERIFICATION_DISAGREEMENT:
            _overturn_original(db, unit, payload.worker_id,
                               error or "verification disagreement")
    _refresh_job_status(db, unit.job_id)
    return ok, (None if ok else (error or "rejected")), result


def _classify(payload: WorkResult, unit: WorkUnit, workload_type: str, op: str,
              original_value: object = None,
              job_params: dict | None = None) -> tuple[bool, str | None, str | None]:
    """Classify a result: (accepted, failure_kind, message).

    Duplicates are judged on reproduction: a value differing from the
    confirmed original is a disagreement, even if the expectation check
    would also fail (reproduction is the stronger, more specific signal).
    """
    if payload.status != "completed":
        return False, WORKER_ERROR, payload.error or "worker reported failure"
    if unit.verify_of is not None and original_value is not None:
        if payload.value != original_value:
            return False, VERIFICATION_DISAGREEMENT, (
                f"verification disagreement: confirmed={original_value!r}, "
                f"duplicate={payload.value!r}"
            )
        if payload.output_hash is not None and payload.output_hash != _hash_of(
            workload_type, op, payload.value
        ):
            return False, HASH_MISMATCH, "output hash mismatch (corrupted result)"
        return True, None, None
    try:
        expected = workload_expected(workload_type, op, unit.range_start, unit.range_end,
                                     job_params)
    except ValueError as exc:
        return False, UNSUPPORTED_WORKLOAD, str(exc)
    if payload.value != expected:
        return False, VALUE_MISMATCH, (
            f"value mismatch: expected {expected!r}, got {payload.value!r}"
        )
    if payload.output_hash is not None and payload.output_hash != _hash_of(
        workload_type, op, payload.value
    ):
        return False, HASH_MISMATCH, "output hash mismatch (corrupted result)"
    return True, None, None


def _hash_of(workload_type: str, op: str, value: object) -> str:
    try:
        return workload_output_hash(workload_type, op, value)
    except ValueError:
        return ""  # unknown workload: hash check is meaningless (value check governs)


def _sampled(unit: WorkUnit, rate: float) -> bool:
    """Deterministic sampling: same unit always replays the same decision."""
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    digest = hashlib.sha256(unit.id.encode()).digest()
    return int.from_bytes(digest[:2], "big") / 65536 < rate


def _maybe_spawn_duplicate(db: Session, job: Job | None, unit: WorkUnit) -> None:
    """Queue a duplicate check unit for an original, sampled by job.verify_sample."""
    if job is None or not _sampled(unit, job.verify_sample or 0.0):
        return
    duplicate = WorkUnit(
        id=str(uuid.uuid4()),
        job_id=unit.job_id,
        sequence=unit.sequence,  # same logical shard as the original
        range_start=unit.range_start,
        range_end=unit.range_end,
        status="queued",
        verify_of=unit.id,
    )
    db.add(duplicate)
    db.commit()
    log.info("duplicate check unit %s spawned for %s (original by %s)",
             duplicate.id, unit.id, unit.assigned_worker_id)


def _confirm_original(db: Session, duplicate: WorkUnit, dup_result: Result) -> None:
    """Record a duplicate's agreement on the original (`verified_by`).

    Disagreement never reaches here: classification rejects a non-reproducing
    duplicate first, and `_overturn_original` handles the fallout.
    """
    original_result = db.get(Result, duplicate.verify_of) if duplicate.verify_of else None
    if original_result is None or dup_result.value != original_result.value:
        return
    original_result.verified_by = dup_result.worker_id
    db.commit()
    reputation.record(db, dup_result.worker_id, reputation.VERIFICATION_AGREED,
                      work_unit_id=duplicate.id)
    log.info("unit %s verified by second worker %s", duplicate.verify_of, dup_result.worker_id)


def _overturn_original(db: Session, duplicate: WorkUnit, disagreer: str,
                       message: str) -> None:
    """A duplicate failed to reproduce the confirmed original: fail *both*.

    The original's result row stays as history (it was accepted), but the
    unit flips completed → failed so the job cannot complete on a disputed
    value (state matrix allows this overturn explicitly).
    """
    original = db.get(WorkUnit, duplicate.verify_of)
    original_result = db.get(Result, duplicate.verify_of) if duplicate.verify_of else None
    if original is None:
        return
    if original_result is not None:
        original_result.ok = False
        original_result.failure_kind = VERIFICATION_DISAGREEMENT
        original_result.error = message
    original.status = "failed"
    db.commit()
    reputation.record(db, disagreer, reputation.VERIFICATION_DISAGREED,
                      work_unit_id=duplicate.id, detail=message)
    log.info("unit %s DISAGREEMENT -> original and duplicate both failed", original.id)


def _close_attempt(db: Session, work_unit_id: str, worker_id: str, ok: bool) -> None:
    attempt = (
        db.query(WorkUnitAttempt)
        .filter_by(work_unit_id=work_unit_id, worker_id=worker_id, outcome=None)
        .order_by(WorkUnitAttempt.started_at.desc())
        .first()
    )
    if attempt is not None:
        attempt.ended_at = datetime.now(timezone.utc)
        attempt.outcome = "completed" if ok else "failed"
        db.commit()


def aggregate_job(db: Session, job_id: str) -> dict | None:
    """Per-status counts + final aggregate once every unit completed.

    The final uses original units only (`verify_of IS NULL`) — duplicates
    confirm values, they must not double-count them.
    """
    job = db.get(Job, job_id)
    if job is None:
        return None
    units = sorted(db.query(WorkUnit).filter_by(job_id=job_id).all(), key=lambda u: u.sequence)
    primaries = [u for u in units if u.verify_of is None]
    counts: dict[str, int] = {}
    for u in units:
        counts[u.status] = counts.get(u.status, 0) + 1
    out: dict = {"counts": counts}
    out["rejections"] = _rejection_summary(db, [u.id for u in units])
    if units and counts.get("completed", 0) == len(units):
        op = (job.params or {}).get("op", "sum")
        if op == "sum":
            total = 0
            for u in primaries:
                r = db.get(Result, u.id)
                if r and isinstance(r.value, (int, float)):
                    total += r.value
            out["final"] = total
        elif op == "hash":
            h = hashlib.sha256()
            for u in primaries:
                r = db.get(Result, u.id)
                h.update(str(r.value if r else "").encode())
            out["final"] = h.hexdigest()
    return out


def _rejection_summary(db: Session, unit_ids: list[str]) -> dict[str, int]:
    kinds: dict[str, int] = {}
    for uid in unit_ids:
        r = db.get(Result, uid)
        if r is not None and not r.ok and r.failure_kind:
            kinds[r.failure_kind] = kinds.get(r.failure_kind, 0) + 1
    return kinds


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


def record_disagreement(db: Session, work_unit_id: str, worker_id: str) -> None:
    """Disagreement evidence for a conflicting late result (409 path).

    Called after rollback by the endpoint: the submitter's value did not
    reproduce the confirmed one, so the submitter — not the original —
    earns the mark.
    """
    reputation.record(db, worker_id, reputation.VERIFICATION_DISAGREED,
                      work_unit_id=work_unit_id,
                      detail="conflicting late result for a completed unit")
