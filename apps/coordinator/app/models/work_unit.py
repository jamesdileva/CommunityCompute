"""WorkUnit model (Sprint 5): the smallest independently executable piece.

Each unit owns a half-open numeric range [start..end] derived from the job's
(total_units, chunk_size) — deterministic ranges make result verification
exact for hello-compute style workloads (implementation-guide §11).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

QUEUED = "queued"
DISPATCHED = "dispatched"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"
INTERRUPTED = "interrupted"


class WorkUnit(Base):
    __tablename__ = "work_units"
    __table_args__ = (UniqueConstraint("job_id", "sequence", name="uq_workunit_job_seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)  # 1-based within the job
    range_start: Mapped[int] = mapped_column(Integer)
    range_end: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default=QUEUED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
