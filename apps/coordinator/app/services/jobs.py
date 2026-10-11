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
from app.schemas.job import JobCreate


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


def create_job(db: Session, payload: JobCreate) -> tuple[Job, list[WorkUnit]]:
    """Create job + all work units atomically. Job params stay immutable."""
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        workload_type=payload.workload_type,
        params=dict(payload.params),  # copy: caller's dict can't mutate stored job
        total_units=payload.total_units,
        chunk_size=payload.chunk_size,
        status="queued",
        verify_sample=payload.verify_sample,
    )
    db.add(job)
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
