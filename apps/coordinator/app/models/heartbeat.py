"""Append-only heartbeat log (Sprint 4, table per architecture §16)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(String(36), ForeignKey("workers.id"), index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    resources: Mapped[dict | None] = mapped_column(JSON)

    # Convenience denormalized columns (helpers, not identity)
    cpu_percent: Mapped[float | None] = mapped_column(Float)
    ram_available_mb: Mapped[int | None] = mapped_column(Integer)
    gpu_percent: Mapped[float | None] = mapped_column(Float)
