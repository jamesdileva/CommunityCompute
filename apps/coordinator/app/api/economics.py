"""Economics endpoints (Sprint 34).

Operator-facing, unauthenticated in the prototype (like the other dashboard
endpoints): exposes the measured cost-per-useful-compute model with its
assumptions kept in a separate block, so a number is never quoted without the
caveats that produced it.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.economics.report import build_report

router = APIRouter()


@router.get("/economics/report")
def economics_report(db: Session = Depends(get_db)) -> dict:
    """Measured inputs + assumed cost constants -> one auditable report."""
    return build_report(db)
