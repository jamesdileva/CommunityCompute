"""Paid-compute billing service (Sprint 37).

Flow (prepaid, integer cents):

    top-up (simulated provider) -> customer balance
    submit a customer job        -> charge = units x workload unit price
    verified original unit       -> contributor share + network fee

Pricing is a per-workload rate card with a configurable network-fee percent.
The price is frozen on the ``JobCharge`` at submit time, so a later rate-card
change never re-prices work already accepted. A duplicate/verification unit
does not earn compensation (only originals do), and an overturned original
voids its contributor share while the network keeps the fee for the attempt.

No payouts are executed and no real money moves: this is the controlled
paid-compute *experiment* the roadmap asks for.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.billing import (
    CHARGE,
    CONTRIBUTOR,
    NETWORK,
    TOPUP,
    BillingEntry,
    CompensationEntry,
    JobCharge,
    Payment,
)
from app.models.job import Job
from app.services import payments

# Cents per verified work unit. These are prototype list prices for the
# paid-compute experiment, not a profitability claim (see docs/pricing.md and
# Sprint 34's measured economics).
DEFAULT_RATE_CARD: dict[str, int] = {
    "hello_compute": 5,
    "stats_range": 3,
    "embeddings": 10,
    "image_generate": 25,
}


class InsufficientFunds(Exception):
    """Prepaid balance below the quoted job charge (maps to HTTP 402)."""

    def __init__(self, need_cents: int, balance_cents: int) -> None:
        super().__init__(f"need {need_cents} cents, have {balance_cents}")
        self.need_cents = need_cents
        self.balance_cents = balance_cents


class InvalidAmount(ValueError):
    """Top-up outside the configured bounds."""


class PaymentFailed(Exception):
    """The provider declined the charge."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def currency() -> str:
    return get_settings().billing_currency.upper()


def rate_card() -> dict[str, int]:
    """Default card merged with the optional JSON override (validated)."""
    card = dict(DEFAULT_RATE_CARD)
    raw = get_settings().pricing_rate_card.strip()
    if not raw:
        return card
    try:
        override = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"PRICING_RATE_CARD is not valid JSON: {exc}") from exc
    if not isinstance(override, dict):
        raise TypeError("PRICING_RATE_CARD must be a JSON object")
    for workload, value in override.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"rate for {workload!r} must be a non-negative integer")
        card[str(workload)] = value
    return card


def network_fee_percent() -> int:
    value = get_settings().pricing_network_fee_percent
    if not (0 <= value <= 100):
        raise ValueError("PRICING_NETWORK_FEE_PERCENT must be between 0 and 100")
    return value


def unit_price(workload_type: str) -> int:
    """Cents per verified unit; unknown/allowlisted-but-unpriced types are 0."""
    return rate_card().get(workload_type, 0)


def split_unit_price(price_cents: int, fee_percent: int) -> tuple[int, int]:
    """(contributor_cents, network_cents); the two always sum to the price."""
    if price_cents < 0:
        raise ValueError("price must be non-negative")
    if not (0 <= fee_percent <= 100):
        raise ValueError("fee percent must be between 0 and 100")
    network = (price_cents * fee_percent + 50) // 100  # half-up, integer cents
    return price_cents - network, network


def quote(workload_type: str, units: int) -> dict:
    """Price snapshot for a job before it is accepted."""
    if units <= 0:
        raise ValueError("units must be positive")
    price = unit_price(workload_type)
    return {
        "workload_type": workload_type,
        "units": units,
        "unit_price_cents": price,
        "amount_cents": price * units,
        "network_fee_percent": network_fee_percent(),
        "currency": currency(),
    }


def balance_cents(db: Session, customer_id: str) -> int:
    """Prepaid balance = SUM of the append-only customer ledger."""
    total = (
        db.query(func.coalesce(func.sum(BillingEntry.amount_cents), 0))
        .filter(BillingEntry.customer_id == customer_id)
        .scalar()
    )
    return int(total or 0)


def _append_entry(
    db: Session, *, customer_id: str, amount_cents: int, kind: str,
    job_id: str | None = None, payment_id: str | None = None,
    description: str | None = None,
) -> BillingEntry:
    entry = BillingEntry(
        id=str(uuid.uuid4()),
        customer_id=customer_id,
        amount_cents=amount_cents,
        kind=kind,
        job_id=job_id,
        payment_id=payment_id,
        description=description,
    )
    db.add(entry)
    return entry


def topup(
    db: Session, customer_id: str, amount_cents: int,
    provider: payments.PaymentProvider | None = None,
) -> tuple[Payment, int]:
    """Charge the provider, credit the prepaid balance, return (payment, balance)."""
    settings = get_settings()
    if amount_cents < settings.billing_min_topup_cents:
        raise InvalidAmount(f"minimum top-up is {settings.billing_min_topup_cents} cents")
    if amount_cents > settings.billing_max_topup_cents:
        raise InvalidAmount(f"maximum top-up is {settings.billing_max_topup_cents} cents")

    provider = provider or payments.get_provider(settings.payment_provider)
    result = provider.charge(
        customer_id=customer_id, amount_cents=amount_cents,
        currency=currency(), reference=f"topup:{customer_id}",
    )
    payment = Payment(
        id=str(uuid.uuid4()),
        customer_id=customer_id,
        provider=result.provider,
        provider_ref=result.provider_ref or "n/a",
        kind=TOPUP,
        amount_cents=amount_cents,
        currency=result.currency,
        status=result.status,
        detail=result.detail,
    )
    db.add(payment)
    db.flush()
    if not result.ok:
        db.commit()
        raise PaymentFailed(result.detail or "payment failed")

    _append_entry(
        db, customer_id=customer_id, amount_cents=amount_cents, kind=TOPUP,
        payment_id=payment.id, description=f"{result.provider} top-up",
    )
    db.commit()
    db.refresh(payment)
    return payment, balance_cents(db, customer_id)


def charge_job(
    db: Session, *, customer_id: str, job_id: str, workload_type: str, units: int
) -> JobCharge:
    """Stage the upfront charge for a customer job (caller commits atomically).

    Raises :class:`InsufficientFunds` *before* anything is added, so a job can
    never exist unpaid. The caller (``jobs.create_job``) commits the job, its
    units, and this charge in one transaction.
    """
    priced = quote(workload_type, units)
    available = balance_cents(db, customer_id)
    if available < priced["amount_cents"]:
        raise InsufficientFunds(priced["amount_cents"], available)

    charge = JobCharge(
        id=str(uuid.uuid4()),
        job_id=job_id,
        customer_id=customer_id,
        workload_type=workload_type,
        units=units,
        unit_price_cents=priced["unit_price_cents"],
        amount_cents=priced["amount_cents"],
        network_fee_percent=priced["network_fee_percent"],
        currency=priced["currency"],
    )
    db.add(charge)
    _append_entry(
        db, customer_id=customer_id, amount_cents=-priced["amount_cents"],
        kind=CHARGE, job_id=job_id,
        description=f"{workload_type}: {units} unit(s) @ {priced['unit_price_cents']}c",
    )
    return charge


def compensate_unit(
    db: Session, *, job: Job | None, work_unit_id: str, worker_id: str
) -> CompensationEntry | None:
    """Credit the contributor/network split for one verified original unit.

    Free open-pool and operator jobs carry no ``JobCharge`` and therefore no
    compensation. Idempotent: re-processing the same unit never pays twice.
    """
    if job is None or job.customer_id is None:
        return None
    charge = db.query(JobCharge).filter_by(job_id=job.id).first()
    if charge is None:
        return None
    existing = (
        db.query(CompensationEntry)
        .filter_by(work_unit_id=work_unit_id, kind=CONTRIBUTOR)
        .first()
    )
    if existing is not None:
        return existing

    contributor_cents, network_cents = split_unit_price(
        charge.unit_price_cents, charge.network_fee_percent
    )
    row = CompensationEntry(
        id=str(uuid.uuid4()),
        worker_id=worker_id,
        job_id=job.id,
        work_unit_id=work_unit_id,
        kind=CONTRIBUTOR,
        amount_cents=contributor_cents,
        currency=charge.currency,
    )
    db.add(row)
    db.add(CompensationEntry(
        id=str(uuid.uuid4()),
        worker_id=None,
        job_id=job.id,
        work_unit_id=work_unit_id,
        kind=NETWORK,
        amount_cents=network_cents,
        currency=charge.currency,
    ))
    db.commit()
    db.refresh(row)
    return row


def void_compensation(db: Session, *, job_id: str, work_unit_id: str) -> bool:
    """Void a contributor's share after a verification overturn (idempotent)."""
    row = (
        db.query(CompensationEntry)
        .filter_by(work_unit_id=work_unit_id, kind=CONTRIBUTOR)
        .first()
    )
    if row is None or row.voided_at is not None:
        return False
    row.voided_at = _now()
    db.commit()
    return True


def customer_summary(db: Session, customer_id: str) -> dict:
    """Prepaid balance, lifetime totals, and this customer's charged jobs."""
    topups = (
        db.query(func.coalesce(func.sum(BillingEntry.amount_cents), 0))
        .filter(BillingEntry.customer_id == customer_id, BillingEntry.kind == TOPUP)
        .scalar()
    )
    charged = (
        db.query(func.coalesce(func.sum(BillingEntry.amount_cents), 0))
        .filter(BillingEntry.customer_id == customer_id, BillingEntry.kind == CHARGE)
        .scalar()
    )
    charges = (
        db.query(JobCharge)
        .filter_by(customer_id=customer_id)
        .order_by(JobCharge.created_at.desc())
        .all()
    )
    return {
        "customer_id": customer_id,
        "currency": currency(),
        "balance_cents": balance_cents(db, customer_id),
        "lifetime_topup_cents": int(topups or 0),
        "lifetime_charged_cents": -int(charged or 0),
        "network_fee_percent": network_fee_percent(),
        "rate_card": rate_card(),
        "charges": [
            {
                "job_id": c.job_id,
                "workload_type": c.workload_type,
                "units": c.units,
                "unit_price_cents": c.unit_price_cents,
                "amount_cents": c.amount_cents,
                "network_fee_percent": c.network_fee_percent,
                "currency": c.currency,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in charges
        ],
    }


def network_summary(db: Session) -> dict:
    """Operator view: charged vs contributor vs network, plus per-workload split."""
    charged = (
        db.query(func.coalesce(func.sum(BillingEntry.amount_cents), 0))
        .filter(BillingEntry.kind == CHARGE)
        .scalar()
    )
    topups = (
        db.query(func.coalesce(func.sum(BillingEntry.amount_cents), 0))
        .filter(BillingEntry.kind == TOPUP)
        .scalar()
    )
    contributor = (
        db.query(func.coalesce(func.sum(CompensationEntry.amount_cents), 0))
        .filter(CompensationEntry.kind == CONTRIBUTOR,
                CompensationEntry.voided_at.is_(None))
        .scalar()
    )
    network = (
        db.query(func.coalesce(func.sum(CompensationEntry.amount_cents), 0))
        .filter(CompensationEntry.kind == NETWORK,
                CompensationEntry.voided_at.is_(None))
        .scalar()
    )
    by_workload = {
        workload: int(total or 0)
        for workload, total in (
            db.query(JobCharge.workload_type,
                     func.coalesce(func.sum(JobCharge.amount_cents), 0))
            .group_by(JobCharge.workload_type)
            .all()
        )
    }
    charged_cents = -int(charged or 0)
    contributor_cents = int(contributor or 0)
    network_cents = int(network or 0)
    return {
        "currency": currency(),
        "network_fee_percent": network_fee_percent(),
        "topup_cents": int(topups or 0),
        "charged_cents": charged_cents,
        "contributor_cents": contributor_cents,
        "network_cents": network_cents,
        "unallocated_cents": charged_cents - contributor_cents - network_cents,
        "jobs": db.query(JobCharge).count(),
        "by_workload": by_workload,
    }


def worker_earnings(db: Session, worker_id: str) -> dict:
    """Contributor accounting: this worker's compensation entries + balance."""
    rows = (
        db.query(CompensationEntry)
        .filter_by(worker_id=worker_id, kind=CONTRIBUTOR)
        .order_by(CompensationEntry.created_at.desc())
        .all()
    )
    return {
        "worker_id": worker_id,
        "currency": currency(),
        "balance_cents": sum(r.amount_cents for r in rows if r.voided_at is None),
        "entries": [
            {
                "job_id": r.job_id,
                "work_unit_id": r.work_unit_id,
                "amount_cents": r.amount_cents,
                "voided": r.voided_at is not None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


def account_balances(db: Session) -> list[dict]:
    """Operator view of every customer's prepaid balance."""
    from app.models.customer import Customer

    return [
        {
            "customer_id": c.id,
            "name": c.name,
            "status": c.status,
            "balance_cents": balance_cents(db, c.id),
            "currency": currency(),
        }
        for c in db.query(Customer).order_by(Customer.created_at.desc()).all()
    ]
