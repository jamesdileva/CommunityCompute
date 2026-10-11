"""Work distribution endpoints (Sprint 6): claim + result submission."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.result import Result
from app.schemas.work import ResultOut, WorkResult
from app.services import work as work_service

log = logging.getLogger("coordinator")

router = APIRouter()


@router.get("/work/{worker_id}")
def claim_work(worker_id: str, db: Session = Depends(get_db)) -> dict:
    """FIFO claim for an online-ish worker. 204 with {} when nothing queued."""
    assignment = work_service.claim_next_unit(db, worker_id)
    if assignment is None:
        return {}
    return assignment.model_dump()


@router.post("/work/{work_unit_id}/result", response_model=ResultOut)
def submit_result(
    work_unit_id: str, payload: WorkResult, db: Session = Depends(get_db)
) -> Result:
    """Verified result upload. Mismatch → 422 with reason (unit marked failed).

    Identity note: the unit records who claimed it; a result submitted by a
    different worker is still processed and recorded under the submitter
    (duplicate execution is cheap here). Sprint 7 leases tighten this.
    """
    try:
        ok, reason, result = work_service.submit_result(db, work_unit_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail={"error": "unknown work unit"})
    if not ok:
        raise HTTPException(
            status_code=422,
            detail={"verification": "failed", "reason": reason},
        )
    return result
