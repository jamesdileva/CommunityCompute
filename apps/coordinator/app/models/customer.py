"""Customer identity + API keys (Sprint 29).

The customer API is a *separate* trust domain from workers (Sprint 20): a
worker bearer token can never act as a customer, and vice versa. Models:

- ``Customer`` — an account that submits work. Prototype scope is deliberately
  thin (name + status); full identity/authorization lands in Sprint 30.
- ``CustomerApiKey`` — the bearer credential a customer sends on `/api/v1`
  calls. **Hash-only storage**: the raw key is shown once at mint and never
  persisted; ``prefix`` is a non-secret label so an operator can tell keys
  apart in listings. Rotation revokes the old row and issues a fresh one.

Keys live in their own table (own hash namespace), so an API key hash can
never collide with or be replayed against a worker credential.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | suspended
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def is_active(self) -> bool:
        return self.status == "active"


class CustomerApiKey(Base):
    __tablename__ = "customer_api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(16))  # first chars of the raw key (display only)
    label: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | revoked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def is_active(self) -> bool:
        return self.status == "active"


def _aware(value: datetime) -> datetime:
    """SQLite strips tzinfo on read; assume UTC before comparing."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
