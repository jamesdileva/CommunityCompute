"""Compute credits (Sprint 28): earn by contributing, spend by consuming.

Rate card v1 (flat, stated plainly — resource-weighted pricing is later):
- 1 verified completed unit (original, not duplicate) → +1 credit.
- 1 submitted unit with a named submitter → -1 credit, taken upfront.

Anti-abuse rules, enforced not documented:
- failures earn nothing; duplicates earn nothing (verification overhead);
- self-dealing earns nothing (worker == job submitter → wash-earning void);
- balances can never go negative (spend is checked before deduction);
- no refunds v1: failed units still cost scheduling, so spent credits stay
  spent (stated in the 402/422 surfaces and here).
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.credit import EARN_VERIFIED_UNIT, SPEND_JOB_SUBMIT, CreditEntry

CREDITS_PER_UNIT = 1


class InsufficientCredits(Exception):
    """Submitter cannot afford the job (maps to HTTP 402)."""

    def __init__(self, worker_id: str, need: int, have: int) -> None:
        super().__init__(f"worker {worker_id} needs {need} credits, has {have}")
        self.worker_id = worker_id
        self.need = need
        self.have = have


def balance(db: Session, worker_id: str) -> int:
    """Current balance = SUM(ledger). Never stored, always derived."""
    return (
        db.query(func.coalesce(func.sum(CreditEntry.amount), 0))
        .filter_by(worker_id=worker_id)
        .scalar()
        or 0
    )


def totals(db: Session, worker_id: str) -> dict:
    """Earned/spent split + balance for one worker."""
    earned = (
        db.query(func.coalesce(func.sum(CreditEntry.amount), 0))
        .filter(CreditEntry.worker_id == worker_id, CreditEntry.amount > 0)
        .scalar()
        or 0
    )
    spent = (
        db.query(func.coalesce(func.sum(CreditEntry.amount), 0))
        .filter(CreditEntry.worker_id == worker_id, CreditEntry.amount < 0)
        .scalar()
        or 0
    )
    return {
        "worker_id": worker_id,
        "balance": earned + spent,
        "earned": earned,
        "spent": -spent,
    }


def earn_verified_unit(
    db: Session, *, worker_id: str, job_id: str, work_unit_id: str,
    submitter_worker_id: str | None,
) -> bool:
    """+1 credit for a verified original completion. False when skipped.

    Skipped (no row, no error): self-dealing — the completing worker is the
    job's own submitter, so paying it would mint credits from nothing.
    """
    if submitter_worker_id is not None and submitter_worker_id == worker_id:
        return False
    db.add(CreditEntry(worker_id=worker_id, amount=CREDITS_PER_UNIT,
                       reason=EARN_VERIFIED_UNIT, job_id=job_id,
                       work_unit_id=work_unit_id))
    db.commit()
    return True


def spend_job_submit(db: Session, *, worker_id: str, job_id: str, units: int) -> None:
    """Stage a -units debit. Raises InsufficientCredits (no partial deduction).

    Deliberately does not commit: the caller commits the debit atomically with
    the job it pays for, so a shortfall can never leave a half-created job.
    """
    need = units * CREDITS_PER_UNIT
    have = balance(db, worker_id)
    if have < need:
        raise InsufficientCredits(worker_id, need, have)
    db.add(CreditEntry(worker_id=worker_id, amount=-need,
                       reason=SPEND_JOB_SUBMIT, job_id=job_id))


def ledger(db: Session, worker_id: str | None = None, limit: int = 100) -> list[dict]:
    """Newest-first ledger rows (audit view)."""
    query = db.query(CreditEntry).order_by(CreditEntry.id.desc())
    if worker_id:
        query = query.filter_by(worker_id=worker_id)
    return [
        {
            "id": r.id,
            "worker_id": r.worker_id,
            "amount": r.amount,
            "reason": r.reason,
            "job_id": r.job_id,
            "work_unit_id": r.work_unit_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in query.limit(min(max(limit, 1), 1000)).all()
    ]
