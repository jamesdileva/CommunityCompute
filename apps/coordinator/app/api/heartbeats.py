"""Heartbeat endpoints (Sprint 4).

Heartbeat = liveness proof + runtime resource snapshot. The coordinator
records it, refreshes last_seen/online, and appends to the log.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.heartbeat import WorkerHeartbeat
from app.models.worker import Worker
from app.schemas.heartbeat import Heartbeat, HeartbeatResponse

log = logging.getLogger("coordinator")

router = APIRouter()


@router.post("/workers/{worker_id}/heartbeat", response_model=HeartbeatResponse)
def receive_heartbeat(
    worker_id: str, payload: Heartbeat, db: Session = Depends(get_db)
) -> HeartbeatResponse:
    if str(payload.worker_id) != worker_id:
        raise HTTPException(status_code=422, detail={"error": "worker_id mismatch"})
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail={"error": "unknown worker"})

    now = datetime.now(timezone.utc)
    resources = payload.resources
    db.add(
        WorkerHeartbeat(
            worker_id=worker_id,
            received_at=now,
            resources=resources.model_dump(),
            cpu_percent=resources.cpu_percent,
            ram_available_mb=resources.ram_available_mb,
            gpu_percent=resources.gpu_percent,
        )
    )
    worker.last_seen = now
    worker.status = "online"
    worker.cpu_percent = resources.cpu_percent
    worker.ram_available_mb = resources.ram_available_mb
    worker.gpu_percent = resources.gpu_percent
    db.commit()
    log.info(
        "heartbeat id=%s cpu=%s%% gpu=%s%% ram_avail=%sMB",
        worker_id, resources.cpu_percent, resources.gpu_percent, resources.ram_available_mb,
    )
    return HeartbeatResponse(status="online", server_time=now.isoformat())


@router.get("/workers/{worker_id}/heartbeats")
def list_heartbeats(worker_id: str, limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    """Recent heartbeat log (newest first). Diagnostics/dashboard precursor."""
    rows = (
        db.query(WorkerHeartbeat)
        .filter_by(worker_id=worker_id)
        .order_by(WorkerHeartbeat.received_at.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )
    return [
        {
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "resources": r.resources,
        }
        for r in rows
    ]
