"""Work-unit attempt records (Sprint 7, table per implementation-guide §6).

One row per attempt (claim → outcome). Attempt outlives the lease: when a
worker vanishes, its attempt is closed as `expired` and the unit returns to
the queue with attempt_number incremented for the next worker.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WorkUnitAttempt(Base):
    __tablename__ = "work_unit_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_unit_id: Mapped[str] = mapped_column(String(36), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str] = mapped_column(String(36), index=True)
    lease_id: Mapped[str | None] = mapped_column(String(36))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(32))  # completed/failed/expired/reclaimed
