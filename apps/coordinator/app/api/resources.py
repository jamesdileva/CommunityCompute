"""Resource telemetry endpoints (Sprint 12)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.sample import ResourceSample
from app.models.worker import Worker
from app.schemas.sample import ResourceReport, SampleOut

router = APIRouter()


@router.post("/workers/{worker_id}/resources", response_model=SampleOut)
def report_resources(
    worker_id: str, payload: ResourceReport, db: Session = Depends(get_db)
) -> SampleOut:
    """Append one telemetry sample. Unknown worker -> 404."""
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail={"error": "unknown worker"})
    sample = ResourceSample(
        worker_id=worker_id,
        sampled_at=datetime.now(timezone.utc),
        **payload.model_dump(),
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


@router.get("/workers/{worker_id}/resources", response_model=list[SampleOut])
def list_resources(
    worker_id: str, limit: int = 50, db: Session = Depends(get_db)
) -> list[SampleOut]:
    """Newest-first samples. limit is clamped to [1, 500]."""
    rows = (
        db.query(ResourceSample)
        .filter_by(worker_id=worker_id)
        .order_by(ResourceSample.sampled_at.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )
    return list(rows)
