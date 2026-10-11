"""Job model (Sprint 5; Sprint 8 adds verify_sample for duplicate verification).

A Job is immutable once created (params/total/chunk never change) — the
work units are the mutable, individually-scheduled pieces.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Job-level states (architecture §11).
QUEUED = "queued"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workload_type: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    total_units: Mapped[int] = mapped_column(Integer)
    chunk_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default=QUEUED)
    # Sprint 8: fraction of units to double-execute for verification (0..1)
    verify_sample: Mapped[float] = mapped_column(Float, default=0.0)
    # Sprint 9: declarative requirements (implementation-guide §10)
    requirements: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
