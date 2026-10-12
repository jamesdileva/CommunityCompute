"""Liveness probe (Sprint 1: proves coordinator alive AND SQLite connected)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import check_database, get_db
from app.models.worker import Worker

SERVICE = "coordinator"
VERSION = "0.1.0-sprint16"

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    if not check_database(db):
        raise HTTPException(
            status_code=503,
            detail={"status": "degraded", "service": SERVICE, "database": {"connected": False}},
        )
    workers = db.query(func.count(Worker.id)).scalar() or 0
    return {
        "status": "ok",
        "service": SERVICE,
        "version": VERSION,
        "database": {"connected": True, "workers": workers},
    }
