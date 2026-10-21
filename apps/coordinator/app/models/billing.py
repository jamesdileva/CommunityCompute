"""Paid-compute billing models (Sprint 37).

Real money is explicitly out of scope for the prototype (AGENTS.md non-goals):
payments are recorded against a **simulated** provider, all amounts are integer
cents, and no payout is ever executed. The tables are append-only where it
matters so balances and compensation can be re-derived and audited:

- ``Payment`` — one provider transaction (top-up/refund), never a secret.
- ``BillingEntry`` — the customer ledger; ``balance = SUM(amount_cents)``.
  Top-ups are positive, job charges negative. Never store a balance.
- ``JobCharge`` — the immutable price snapshot for one customer job (unit
  price and network-fee percent are frozen at submit so later rate changes
  cannot re-price work in flight).
- ``CompensationEntry`` — contributor / network split of verified units.
  ``worker_id`` is NULL for the network's share. Voiding a disputed original
  sets ``voided_at`` (never deletes history) and only affects the contributor
  share; the network fee is retained as the cost of the failed attempt.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Payment kinds
TOPUP = "topup"
REFUND = "refund"
# Billing entry kinds
CHARGE = "charge"
# Compensation kinds
CONTRIBUTOR = "contributor"
NETWORK = "network"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    provider_ref: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # topup | refund
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(16))  # succeeded | failed
    detail: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BillingEntry(Base):
    __tablename__ = "billing_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer)  # signed: +credit / -debit
    kind: Mapped[str] = mapped_column(String(16))  # topup | charge | refund | adjustment
    job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    payment_id: Mapped[str | None] = mapped_column(String(36))
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobCharge(Base):
    __tablename__ = "job_charges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    workload_type: Mapped[str] = mapped_column(String(64))
    units: Mapped[int] = mapped_column(Integer)
    unit_price_cents: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(Integer)
    network_fee_percent: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompensationEntry(Base):
    __tablename__ = "compensation_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    worker_id: Mapped[str | None] = mapped_column(String(36), index=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    work_unit_id: Mapped[str | None] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # contributor | network
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
