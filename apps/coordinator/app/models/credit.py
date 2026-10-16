"""Credit ledger (Sprint 28): non-cash internal economics.

Append-only rows; a worker's balance is always SUM(amount) — never a stored
field that could drift from history. Positive rows are issuance (verified
contribution); negative rows are consumption (job submission). Reasons are
mandatory: every credit movement must say why (auditability is the point).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Issuance reasons.
EARN_VERIFIED_UNIT = "earn_verified_unit"
# Consumption reasons.
SPEND_JOB_SUBMIT = "spend_job_submit"

REASONS = frozenset({EARN_VERIFIED_UNIT, SPEND_JOB_SUBMIT})


class CreditEntry(Base):
    __tablename__ = "credit_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[int] = mapped_column(Integer)  # +earn / -spend, never 0
    reason: Mapped[str] = mapped_column(String(32), index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    work_unit_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
