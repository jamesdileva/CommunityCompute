"""Reputation history (Sprint 23): append-only worker conduct log.

One row per scored outcome. The score itself is always *derived* (see
services/reputation.py) — this table is evidence, never a cached verdict,
so the formula can evolve without migrations.

Event vocabulary (closed set, enforced by the service layer):
- result_accepted / result_rejected (with failure_kind on rejection)
- lease_expired (worker vanished mid-lease; fault-tolerance signal, S7)
- verification_agreed (duplicate confirmed the original)
- verification_disagreed (duplicate contradicted the original)
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

RESULT_ACCEPTED = "result_accepted"
RESULT_REJECTED = "result_rejected"
LEASE_EXPIRED = "lease_expired"
VERIFICATION_AGREED = "verification_agreed"
VERIFICATION_DISAGREED = "verification_disagreed"

EVENTS = frozenset({
    RESULT_ACCEPTED,
    RESULT_REJECTED,
    LEASE_EXPIRED,
    VERIFICATION_AGREED,
    VERIFICATION_DISAGREED,
})


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    event: Mapped[str] = mapped_column(String(32), index=True)
    failure_kind: Mapped[str | None] = mapped_column(String(32))
    work_unit_id: Mapped[str | None] = mapped_column(String(36))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
