"""Authentication tables (Sprint 20).

Two tables, one principle: **the coordinator only ever stores hashes.**

- ``EnrollmentToken`` — the operator mints one; the raw value is shown once
  (use cases in roadmap: bootstrap a new machine, re-key a wiped credential).
  Stored hashed, single-use (``used_by``/``used_at`` on redemption), optional
  note and expiry. Minting is operator-only via `POST /enrollment-tokens`.
- ``WorkerCredential`` — the long-lived bearer credential issued at
  enrollment. Stored hashed; the raw token lives only on the worker (credential
  file next to its ID). Status active/revoked + ``last_seen`` make revocation
  and auditing cheap; rotation issues a fresh hash and revokes the old row.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EnrollmentToken(Base):
    __tablename__ = "enrollment_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    note: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def active(self, now: datetime | None = None) -> bool:
        if self.used_at is not None:
            return False
        if self.expires_at is None:
            return True
        now = now or datetime.now(timezone.utc)
        return _aware(self.expires_at) > now


class WorkerCredential(Base):
    __tablename__ = "worker_credentials"

    # worker_id == credential subject: one active credential per worker.
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    worker_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | revoked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def is_active(self) -> bool:
        return self.status == "active"


def _aware(value: datetime) -> datetime:
    """SQLite strips tzinfo on read; assume UTC before comparing."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
