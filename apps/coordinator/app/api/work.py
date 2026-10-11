"""Work distribution endpoints (Sprint 6/7): claim (leases) + result submission."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.result import Result
from app.schemas.work import ResultOut, WorkResult
from app.services import work as work_service
from app.services.work import Conflict

log = logging.getLogger("coordinator")

router = APIRouter()


@router.post("/work/{worker_id}/claim")
def claim_work(worker_id: str, db: Session = Depends(get_db)) -> dict:
    """Expire stale leases, then FIFO-claim the oldest queued unit ({} when idle)."""
    assignment = work_service.claim_next_unit(db, worker_id)
    if assignment is None:
        return {}
    return assignment.model_dump()


@router.post("/work/{work_unit_id}/result", response_model=ResultOut)
def submit_result(
    work_unit_id: str, payload: WorkResult, db: Session = Depends(get_db)
) -> Result:
    """Verified result upload.

    - 404 unknown unit
    - 422 verification failure (unit marked failed)
    - 409 already completed elsewhere (only an identical resubmission is OK)
    """
    try:
        ok, reason, result = work_service.submit_result(db, work_unit_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail={"error": "unknown work unit"})
    except Conflict:
        db.rollback()
        raise HTTPException(
            status_code=409, detail={"error": "already completed by another worker"}
        )
    if not ok:
        raise HTTPException(
            status_code=422,
            detail={
                "verification": "failed",
                "reason": reason,
                "failure_kind": result.failure_kind,
            },
        )
    return result