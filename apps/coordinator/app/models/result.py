"""Result persistence (Sprint 6).

One row per completed/failed work unit; a completed unit's value is verified
against the coordinator's own deterministic expectation before its unit is
marked completed.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Result(Base):
    __tablename__ = "results"

    work_unit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    worker_id: Mapped[str | None] = mapped_column(String(36), index=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    value: Mapped[object] = mapped_column(JSON)
    output_hash: Mapped[str | None] = mapped_column(Text)
    execution_ms: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
