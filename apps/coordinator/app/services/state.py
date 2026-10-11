"""Work-unit / job state machine (Sprint 5; transition rules validated now,
driven by the scheduler in Sprints 6-7, execution in Sprint 6).

Rules per architecture §11: units move forward one step at a time; failure
or disappearance lands in INTERRUPTED, which returns the unit to QUEUED
(retry) — nothing disappears off the state graph.
"""

from app.models import work_unit as wu
from app.models import job as job_model

_UNIT_TRANSITIONS: dict[str, set[str]] = {
    wu.QUEUED: {wu.DISPATCHED, wu.CANCELLED},
    wu.DISPATCHED: {wu.RUNNING, wu.QUEUED, wu.FAILED, wu.INTERRUPTED},
    wu.RUNNING: {wu.COMPLETED, wu.FAILED, wu.INTERRUPTED, wu.CANCELLED},
    wu.INTERRUPTED: {wu.QUEUED, wu.FAILED},  # requeue for retry (expired lease)
    wu.FAILED: {wu.QUEUED},  # manual/auto retry
    wu.COMPLETED: {wu.FAILED},  # verification overturn (duplicate disagreed)
    # terminal: CANCELLED -> {}
}

_JOB_TRANSITIONS: dict[str, set[str]] = {
    job_model.QUEUED: {job_model.RUNNING, job_model.CANCELLED, job_model.FAILED},
    job_model.RUNNING: {job_model.COMPLETED, job_model.FAILED, job_model.CANCELLED},
    # terminal: COMPLETED, FAILED, CANCELLED -> {}
}


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in _UNIT_TRANSITIONS.get(from_status, set())


def can_job_transition(from_status: str, to_status: str) -> bool:
    return to_status in _JOB_TRANSITIONS.get(from_status, set())
