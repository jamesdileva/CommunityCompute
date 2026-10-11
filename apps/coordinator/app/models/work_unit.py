"""WorkUnit model (Sprint 5; S6 assignment; S7 leasing; S8 verify_of duplicates).

Duplicate verification units share the original's sequence (same logical
shard) and are distinguished by `verify_of`. The (job_id, sequence) unique
constraint was therefore dropped — creation-time code still guarantees one
original per sequence (duplicates are the only sharers).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

QUEUED = "queued"
DISPATCHED = "dispatched"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"
INTERRUPTED = "interrupted"

# Lease-held states: a unit in these states holds a live lease until it ends.
LEASE_STATES = (DISPATCHED, RUNNING)


class WorkUnit(Base):
    __tablename__ = "work_units"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)  # 1-based within the job
    range_start: Mapped[int] = mapped_column(Integer)
    range_end: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default=QUEUED)
    assigned_worker_id: Mapped[str | None] = mapped_column(String(36), index=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Sprint 7 lease columns (implementation-guide §14)
    lease_id: Mapped[str | None] = mapped_column(String(36), index=True)
    lease_worker_id: Mapped[str | None] = mapped_column(String(36))
    lease_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_number: Mapped[int] = mapped_column(Integer, default=0)
    # Sprint 8: duplicate-verification unit points at its original (None = original)
    verify_of: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
