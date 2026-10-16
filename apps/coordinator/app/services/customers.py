"""Customer account + API-key service (Sprint 29).

Mirrors the Sprint 20 worker credential service but for a **separate trust
domain**: customer keys are stored hashed, verified per call, and checked
against their owning customer's status. Operators mint customers and rotate
or revoke keys; the raw key is returned exactly once.

Usage accounting is a read-only rollup over the jobs a customer owns
(``Job.customer_id``) and their work units — no billing in the prototype
(architecture §21: no real money), just visibility.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.customer import Customer, CustomerApiKey
from app.models.job import Job
from app.models.work_unit import WorkUnit
from app.services.auth import hash_token

KEY_PREFIX = "cc_"
_DISPLAY_PREFIX_LEN = 11  # "cc_" + 8 chars of the random body


def new_customer_id() -> str:
    """Server-minted customer id (uuid4) — identity is never client-chosen."""
    return str(uuid.uuid4())


def _new_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def create_customer(
    db: Session, name: str, label: str | None = None
) -> tuple[Customer, str]:
    """Create a customer + its first API key; returns (customer, raw_key)."""
    customer = Customer(id=new_customer_id(), name=name, status="active")
    db.add(customer)
    db.flush()  # assign PK for the FK before the key row
    _, raw = issue_key(db, customer.id, label=label)
    db.commit()
    db.refresh(customer)
    return customer, raw


def issue_key(
    db: Session, customer_id: str, label: str | None = None
) -> tuple[CustomerApiKey, str]:
    """Mint a fresh active key; returns (row, raw). Raw is shown once."""
    raw = _new_key()
    row = CustomerApiKey(
        id=secrets.token_hex(6),
        customer_id=customer_id,
        key_hash=hash_token(raw),
        prefix=raw[:_DISPLAY_PREFIX_LEN],
        label=label,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw


def verify_key(db: Session, raw: str | None) -> Customer | None:
    """Return the active customer for a raw API key, or None (refreshes last_seen).

    Fails closed on: blank/missing key, unknown hash, revoked key, or a
    suspended customer — a valid key for an inactive account stops working.
    """
    if not raw:
        return None
    row = (
        db.query(CustomerApiKey)
        .filter(CustomerApiKey.key_hash == hash_token(raw))
        .first()
    )
    if row is None or not row.is_active():
        return None
    customer = db.get(Customer, row.customer_id)
    if customer is None or not customer.is_active():
        return None
    row.last_seen = datetime.now(timezone.utc)
    db.commit()
    return customer


def rotate_key(
    db: Session, customer_id: str, label: str | None = None
) -> tuple[bool, str, str | None]:
    """Revoke the customer's active keys and issue a fresh one."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        return False, "unknown customer", None
    now = datetime.now(timezone.utc)
    for row in (
        db.query(CustomerApiKey).filter_by(customer_id=customer_id, status="active").all()
    ):
        row.status = "revoked"
        row.revoked_at = now
    _, raw = issue_key(db, customer_id, label=label)
    db.commit()
    return True, "rotated", raw


def revoke_customer(db: Session, customer_id: str) -> tuple[bool, str, int]:
    """Revoke every active key for a customer (account stays, access stops)."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        return False, "unknown customer", 0
    now = datetime.now(timezone.utc)
    rows = (
        db.query(CustomerApiKey).filter_by(customer_id=customer_id, status="active").all()
    )
    for row in rows:
        row.status = "revoked"
        row.revoked_at = now
    db.commit()
    return True, "revoked", len(rows)


def owns_job(db: Session, customer_id: str, job_id: str) -> Job | None:
    """The job iff this customer owns it (else None → caller returns 404)."""
    job = db.get(Job, job_id)
    if job is None or job.customer_id != customer_id:
        return None
    return job


def list_customers(db: Session) -> list[dict]:
    """Non-secret customer view for the operator."""
    rows = db.query(Customer).order_by(Customer.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "status": c.status,
            "active_keys": db.query(CustomerApiKey)
            .filter_by(customer_id=c.id, status="active")
            .count(),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]


def list_keys(db: Session, customer_id: str | None = None) -> list[dict]:
    """Non-secret key view (prefix + status, never the hash)."""
    query = db.query(CustomerApiKey)
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    rows = query.order_by(CustomerApiKey.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "customer_id": r.customer_id,
            "prefix": r.prefix,
            "label": r.label,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "last_seen": r.last_seen.isoformat() if r.last_seen else None,
            "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
        }
        for r in rows
    ]


def usage(db: Session, customer_id: str) -> dict:
    """Read-only usage rollup: jobs owned + their unit status/workload split."""
    jobs = db.query(Job).filter_by(customer_id=customer_id).all()
    units_by_status: dict[str, int] = {}
    units_by_workload: dict[str, int] = {}
    for job in jobs:
        units = db.query(WorkUnit).filter_by(job_id=job.id).all()
        units_by_workload[job.workload_type] = (
            units_by_workload.get(job.workload_type, 0) + len(units)
        )
        for unit in units:
            units_by_status[unit.status] = units_by_status.get(unit.status, 0) + 1
    return {
        "customer_id": customer_id,
        "jobs": len(jobs),
        "units": sum(units_by_status.values()),
        "units_by_status": units_by_status,
        "units_by_workload": units_by_workload,
    }
