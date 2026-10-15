"""Auditable contribution records (Sprint 27).

One row per completed work unit: who computed what, how long it took, and
whether the value still stands. Append-only by design — the single allowed
mutation is `voided_at` on verification overturn (the dispute history stays
in results + reputation events regardless).

This table is the ledger Sprint 28+ economics will settle against; it must
be complete and self-explanatory without joining five other tables.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ContributionRecord(Base):
    __tablename__ = "contribution_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_unit_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    worker_id: Mapped[str] = mapped_column(String(36), index=True)
    workload_type: Mapped[str] = mapped_column(String(64))
    execution_ms: Mapped[float | None] = mapped_column(Float)
    cpu_time_ms: Mapped[float | None] = mapped_column(Float)
    gpu_time_ms: Mapped[float | None] = mapped_column(Float)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    verified_by: Mapped[str | None] = mapped_column(String(36))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
