"""Worker registry table (Sprint 1; Sprint 4 adds last-seen-based availability)."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Statuses a worker can be in. Derived "online"/"offline" come from last_seen
# vs the heartbeat timeout; explicit states (paused) arrive later (Sprint 11).
ONLINE = "online"
OFFLINE = "offline"


class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    worker_version: Mapped[str | None] = mapped_column(String(32))
    hostname: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Latest reported resource snapshot (Sprint 4; heartbeat convenience copy)
    cpu_percent: Mapped[float | None] = mapped_column(Float)
    ram_available_mb: Mapped[int | None] = mapped_column(Integer)
    gpu_percent: Mapped[float | None] = mapped_column(Float)
