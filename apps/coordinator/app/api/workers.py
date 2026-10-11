"""Worker registry endpoints (Sprint 2: register + list; heartbeat lands in Sprint 4)."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.worker import Worker
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
    return list(db.query(Worker).order_by(Worker.first_seen).all())
