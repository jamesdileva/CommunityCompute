"""Append-only resource telemetry (Sprint 12).

One row per sample tick (cpu/ram/gpu/vram/temp). High-write + bounded use:
the API serves the newest N for dashboards; older rows are diagnostics.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ResourceSample(Base):
    __tablename__ = "worker_resource_samples"
    __table_args__ = (Index("ix_samples_worker_time", "worker_id", "sampled_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(String(36), ForeignKey("workers.id"), index=True)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    cpu_percent: Mapped[float | None] = mapped_column(Float)
    ram_available_mb: Mapped[int | None] = mapped_column(Integer)
    ram_used_percent: Mapped[float | None] = mapped_column(Float)
    gpu_percent: Mapped[float | None] = mapped_column(Float)
    gpu_vram_used_mb: Mapped[int | None] = mapped_column(Integer)
    gpu_temp_c: Mapped[float | None] = mapped_column(Float)
