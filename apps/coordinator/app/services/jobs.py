"""Job + work-unit creation service (Sprint 5).

create_job() is the single transactional entry point: the job and all its
work units are created together, so a job never exists without its full
decomposition. Units are deterministic ranges (1-based, last chunk clamped).
"""

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.work_unit import WorkUnit
from app.models.worker import Worker
from app.schemas.job import JobCreate
from app.services import billing, credits
from app.services.isolation import scope_for_customer
from app.services.workloads import workload_version


def plan_units(total_units: int, chunk_size: int) -> list[tuple[int, int]]:
    """Deterministic (start, end) ranges, 1-based inclusive; last chunk clamped."""
    ranges: list[tuple[int, int]] = []
    start = 1
    while start <= total_units:
        end = min(start + chunk_size - 1, total_units)
        ranges.append((start, end))
        start = end + 1
    return ranges


def unit_count(total_units: int, chunk_size: int) -> int:
    return math.ceil(total_units / chunk_size)


def create_job(
    db: Session, payload: JobCreate, *, customer_id: str | None = None
) -> tuple[Job, list[WorkUnit]]:
    """Create job + all work units atomically. Job params stay immutable.

    Sprint 28: a named submitter pays 1 credit per unit upfront (402 when
    short); anonymous submits stay free (backwards compatible open pool).
    Sprint 29: ``customer_id`` (set by the customer API from the authenticated
    key, never client-supplied) records ownership for status/result/usage.
    Sprint 37: a customer job is prepaid — the balance is debited for
    ``units x unit price`` in the same transaction (402 when short).
    """
    submitter = payload.submitter_worker_id
    if submitter is not None and db.get(Worker, submitter) is None:
        raise KeyError("unknown submitter worker")
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        workload_type=payload.workload_type,
        params=dict(payload.params),  # copy: caller's dict can't mutate stored job
        total_units=payload.total_units,
        chunk_size=payload.chunk_size,
        status="queued",
        verify_sample=payload.verify_sample,
        requirements=payload.requirements.model_dump(exclude_unset=True),
        submitter_worker_id=submitter,
        customer_id=customer_id,
        workload_version=workload_version(payload.workload_type),
        isolation_scope=scope_for_customer(customer_id),
    )
    units = [
        WorkUnit(
            id=str(uuid.uuid4()),
            job_id=job_id,
            sequence=seq,
            range_start=start,
            range_end=end,
            status="queued",
        )
        for seq, (start, end) in enumerate(plan_units(job.total_units, job.chunk_size), start=1)
    ]
    # Stage the debit first (raises 402 before anything is written), then commit
    # job + units + ledger row in one transaction — no orphaned job on shortfall.
    if submitter is not None:
        credits.spend_job_submit(db, worker_id=submitter, job_id=job_id,
                                 units=len(units))
    if customer_id is not None:
        billing.charge_job(db, customer_id=customer_id, job_id=job_id,
                           workload_type=job.workload_type, units=len(units))
    db.add(job)
    db.add_all(units)
    db.commit()
    db.refresh(job)
    return job, units


def job_status(db: Session, job_id: str) -> JobStatusData | None:
    """Job + per-status unit counts + units (newest-compatible plain data)."""
    job = db.get(Job, job_id)
    if job is None:
        return None
    units = list(db.query(WorkUnit).filter_by(job_id=job_id).order_by(WorkUnit.sequence).all())
    counts: dict[str, int] = {}
    for u in units:
        counts[u.status] = counts.get(u.status, 0) + 1
    return JobStatusData(job=job, units=units, counts=counts)


class JobStatusData:
    """Internal carrier; the API layer converts to JobStatusOut."""

    def __init__(self, job: Job, units: list[WorkUnit], counts: dict[str, int]) -> None:
        self.job = job
        self.units = units
        self.counts = counts


def list_jobs(db: Session) -> list[Job]:
    return list(db.query(Job).order_by(Job.created_at.desc()).all())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
