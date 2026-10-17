"""Tenant isolation (Sprint 30): one authoritative owner/scope check.

Customer A must never reach Customer B's workload or data. Every read that
returns customer data routes through :func:`authorize_job`; a denial is a
`AccessDenied` (the API maps it to 404, so a foreign job's existence never
leaks) and is logged for audit.

The boundary is the **isolation scope** stored on the job: ``customer:<id>``
for customer work, ``operator`` for dashboard/operator-submitted work. The
scope is derived from the authenticated identity — never from request input.
"""

import logging

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.job import Job

log = logging.getLogger("coordinator")

SCOPE_OPERATOR = "operator"


def customer_scope(customer_id: str) -> str:
    return f"customer:{customer_id}"


def scope_for_customer(customer_id: str | None) -> str:
    """The scope a new job is created under."""
    return customer_scope(customer_id) if customer_id else SCOPE_OPERATOR


def job_scope(job: Job) -> str:
    """The scope a job belongs to (stored, else derived for pre-Sprint-30 rows)."""
    return job.isolation_scope or scope_for_customer(job.customer_id)


class AccessDenied(Exception):
    """The actor may not touch this job. The API layer maps this to 404."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"access denied for job {job_id}")
        self.job_id = job_id


def authorize_job(db: Session, customer: Customer, job_id: str) -> Job:
    """Return the job iff the customer owns its scope; otherwise raise (fail closed)."""
    job = db.get(Job, job_id)
    if job is None or job_scope(job) != customer_scope(customer.id):
        log.info("isolation: denied customer=%s job=%s", customer.id, job_id)
        raise AccessDenied(job_id)
    return job
