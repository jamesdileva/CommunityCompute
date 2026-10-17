"""Per-customer resource quotas (Sprint 30).

Enforced at ``POST /api/v1/jobs`` so a single customer can't monopolize the
network: caps on units per job, concurrent in-flight jobs, and total units in
flight. All limits are settings-driven (``CUSTOMER_MAX_*``) with prototype
defaults; raising them is an operator decision, not a code change.

Read-only usage here powers ``GET /api/v1/quota``.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.job import Job
from app.models.work_unit import WorkUnit

IN_FLIGHT_JOB_STATUSES = ("queued", "running")
IN_FLIGHT_UNIT_STATUSES = ("queued", "dispatched", "running")


class QuotaExceeded(Exception):
    """A customer submit would break a cap. The API maps this to 413/429."""

    def __init__(self, scope: str, limit: int, current: int, requested: int = 0) -> None:
        super().__init__(f"quota {scope}: limit {limit}, current {current}")
        self.scope = scope
        self.limit = limit
        self.current = current
        self.requested = requested


def limits() -> dict:
    settings = get_settings()
    return {
        "max_units_per_job": settings.customer_max_units_per_job,
        "max_in_flight_jobs": settings.customer_max_in_flight_jobs,
        "max_units_in_flight": settings.customer_max_units_in_flight,
    }


def in_flight_jobs(db: Session, customer_id: str) -> int:
    return (
        db.query(func.count(Job.id))
        .filter(Job.customer_id == customer_id, Job.status.in_(IN_FLIGHT_JOB_STATUSES))
        .scalar()
        or 0
    )


def units_in_flight(db: Session, customer_id: str) -> int:
    return (
        db.query(func.count(WorkUnit.id))
        .join(Job, Job.id == WorkUnit.job_id)
        .filter(Job.customer_id == customer_id,
                WorkUnit.status.in_(IN_FLIGHT_UNIT_STATUSES))
        .scalar()
        or 0
    )


def usage(db: Session, customer_id: str) -> dict:
    return {
        "in_flight_jobs": in_flight_jobs(db, customer_id),
        "units_in_flight": units_in_flight(db, customer_id),
    }


def check_submit(db: Session, customer_id: str, requested_units: int) -> None:
    """Raise QuotaExceeded if this submit would break a cap (no partial write)."""
    caps = limits()
    if requested_units > caps["max_units_per_job"]:
        raise QuotaExceeded("units_per_job", caps["max_units_per_job"],
                            requested_units, requested_units)
    current_jobs = in_flight_jobs(db, customer_id)
    if current_jobs + 1 > caps["max_in_flight_jobs"]:
        raise QuotaExceeded("in_flight_jobs", caps["max_in_flight_jobs"], current_jobs)
    current_units = units_in_flight(db, customer_id)
    if current_units + requested_units > caps["max_units_in_flight"]:
        raise QuotaExceeded("units_in_flight", caps["max_units_in_flight"],
                            current_units, requested_units)
