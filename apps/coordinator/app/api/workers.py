"""Worker registry endpoints (Sprint 2: register + list; Sprint 3: capabilities + detail)."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.capability import WorkerCapability
from app.models.worker import Worker
from app.schemas.capability import CapabilityProfile
from app.schemas.worker import WorkerOut, WorkerRegistration

log = logging.getLogger("coordinator")

router = APIRouter(prefix="/workers", tags=["workers"])


@router.post("/register", response_model=WorkerOut)
def register_worker(payload: WorkerRegistration, db: Session = Depends(get_db)) -> Worker:
    """Idempotent upsert: re-registering the same ID refreshes version/host/seen timestamps."""
    wid = str(payload.worker_id)
    now = datetime.now(timezone.utc)
    worker = db.get(Worker, wid)
    if worker is None:
        worker = Worker(
            id=wid,
            worker_version=payload.worker_version,
            hostname=payload.hostname,
            status="online",
            last_seen=now,
        )
        db.add(worker)
        log.info("worker registered id=%s version=%s host=%s", wid, payload.worker_version,
                 payload.hostname)
    else:
        worker.worker_version = payload.worker_version
        worker.hostname = payload.hostname
        worker.status = "online"
        worker.last_seen = now
        log.info("worker re-registered id=%s version=%s", wid, payload.worker_version)
    db.commit()
    db.refresh(worker)
    return worker


@router.get("", response_model=list[WorkerOut])
def list_workers(db: Session = Depends(get_db)) -> list[Worker]:
    """All workers with their latest capability profiles (None when never reported)."""
    workers = list(db.query(Worker).order_by(Worker.first_seen).all())
    caps = {
        c.worker_id: c.profile
        for c in db.query(WorkerCapability).all()
    }
    for w in workers:
        w.capabilities = caps.get(w.id)  # attached transiently for WorkerOut serialization
    return workers


@router.get("/{worker_id}", response_model=WorkerOut)
def get_worker(worker_id: str, db: Session = Depends(get_db)) -> Worker:
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail={"error": "unknown worker"})
    cap = db.get(WorkerCapability, worker_id)
    worker.capabilities = cap.profile if cap else None
    return worker


@router.post("/{worker_id}/capabilities", response_model=CapabilityProfile)
def report_capabilities(
    worker_id: str, payload: CapabilityProfile, db: Session = Depends(get_db)
) -> CapabilityProfile:
    """Upsert a worker's capability profile. Unknown worker → 404; bad shape → 422."""
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail={"error": "unknown worker"})
    now = datetime.now(timezone.utc)
    cap = db.get(WorkerCapability, worker_id)
    if cap is None:
        cap = WorkerCapability(worker_id=worker_id, profile=payload.model_dump())
        db.add(cap)
        log.info("capabilities stored id=%s gpus=%d", worker_id, len(payload.gpus))
    else:
        cap.profile = payload.model_dump()
        cap.updated_at = now
        log.info("capabilities updated id=%s gpus=%d", worker_id, len(payload.gpus))
    db.commit()
    return payload
