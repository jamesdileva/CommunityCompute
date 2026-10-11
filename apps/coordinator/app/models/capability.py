"""Worker capability persistence (Sprint 3, table per architecture §16)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WorkerCapability(Base):
    __tablename__ = "worker_capabilities"

    worker_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workers.id"), primary_key=True
    )
    profile: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
