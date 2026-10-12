"""Result persistence (Sprint 6; Sprint 8: classified failures + duplicate confirmation).

`failure_kind` says *why* a result failed (value_mismatch, hash_mismatch,
worker_error, unsupported_workload, verification_disagreement) instead of a
free-form string alone. `verified_by` names the confirming worker when a
duplicate execution agreed with the original (Sprint 8 duplication).
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
    failure_kind: Mapped[str | None] = mapped_column(String(32), index=True)
    verified_by: Mapped[str | None] = mapped_column(String(36))
    metrics: Mapped[dict | None] = mapped_column(JSON)  # Sprint 15: docs/dim/cache_hit/...
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
