"""Sprint 5: state-machine transition matrix."""

from app.models import job as job_model
from app.models import work_unit as wu
from app.services.state import can_job_transition, can_transition


def test_unit_happy_path():
    assert can_transition(wu.QUEUED, wu.DISPATCHED)
    assert can_transition(wu.DISPATCHED, wu.RUNNING)
    assert can_transition(wu.RUNNING, wu.COMPLETED)


def test_unit_interrupted_returns_to_queue():
    assert can_transition(wu.RUNNING, wu.INTERRUPTED)
    assert can_transition(wu.INTERRUPTED, wu.QUEUED)  # lease expired → retry


def test_unit_rejects_illegal_jumps():
    assert not can_transition(wu.QUEUED, wu.RUNNING)  # no skipping dispatch
    assert not can_transition(wu.QUEUED, wu.COMPLETED)
    assert not can_transition(wu.CANCELLED, wu.QUEUED)
    assert not can_transition("bogus", wu.RUNNING)


def test_completed_can_fail_on_verification_overturn():
    # duplicate checker disagreed -> completed flips to failed (Sprint 8)
    assert can_transition(wu.COMPLETED, wu.FAILED)
    assert not can_transition(wu.COMPLETED, wu.RUNNING)


def test_job_transitions():
    assert can_job_transition(job_model.QUEUED, job_model.RUNNING)
    assert can_job_transition(job_model.RUNNING, job_model.COMPLETED)
    assert not can_job_transition(job_model.COMPLETED, job_model.RUNNING)
    assert not can_job_transition("bogus", job_model.RUNNING)
