"""Worker reliability scoring (Sprint 23).

Score = Laplace-smoothed success rate over scored outcomes:

    score = (accepted + agreed + 1) / (scored_outcomes + 2)

Smoothing (the +1/+2) keeps new workers near 0.5 instead of 0%/100% on
their first units — a cold-start prior, not a reward. Rejections,
expiries, and disagreements all count against; agreements count for.
`leases expired` also feeds the fault-tolerance picture (S7 data, S23 use).

Below MIN_EVIDENCE scored outcomes the worker is "unrated" (score None):
the scheduler must treat unrated as eligible-but-unproven, never as bad.
Reputation feeds scheduling only in Sprint 31; until then it is measured
and exposed, not acted upon.
"""

from sqlalchemy.orm import Session

from app.models.reputation import (
    EVENTS,
    LEASE_EXPIRED,
    RESULT_ACCEPTED,
    RESULT_REJECTED,
    VERIFICATION_AGREED,
    VERIFICATION_DISAGREED,
    ReputationEvent,
)

MIN_EVIDENCE = 5

# Outcomes that count for/against the smoothed rate.
POSITIVE = frozenset({RESULT_ACCEPTED, VERIFICATION_AGREED})
NEGATIVE = frozenset({RESULT_REJECTED, LEASE_EXPIRED, VERIFICATION_DISAGREED})


def record(
    db: Session,
    worker_id: str,
    event: str,
    *,
    failure_kind: str | None = None,
    work_unit_id: str | None = None,
    detail: str | None = None,
) -> ReputationEvent:
    """Append one reputation event. Raises ValueError on unknown events."""
    if event not in EVENTS:
        raise ValueError(f"unknown reputation event {event!r}")
    row = ReputationEvent(
        worker_id=worker_id,
        event=event,
        failure_kind=failure_kind,
        work_unit_id=work_unit_id,
        detail=detail,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def reliability(db: Session, worker_id: str, limit: int = 50) -> dict:
    """Score + counts + recent history for one worker ({} when unknown worker)."""
    from app.models.worker import Worker

    if db.get(Worker, worker_id) is None:
        raise KeyError("unknown worker")
    rows = (
        db.query(ReputationEvent)
        .filter_by(worker_id=worker_id)
        .order_by(ReputationEvent.created_at.desc(), ReputationEvent.id.desc())
        .all()
    )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.event] = counts.get(row.event, 0) + 1
    positive = sum(counts.get(e, 0) for e in POSITIVE)
    negative = sum(counts.get(e, 0) for e in NEGATIVE)
    total = positive + negative
    score: float | None = None
    if total >= MIN_EVIDENCE:
        score = round((positive + 1) / (total + 2), 4)
    kinds: dict[str, int] = {}
    for row in rows:
        if row.event == RESULT_REJECTED and row.failure_kind:
            kinds[row.failure_kind] = kinds.get(row.failure_kind, 0) + 1
    return {
        "worker_id": worker_id,
        "score": score,
        "rated": score is not None,
        "outcomes": total,
        "accepted": counts.get(RESULT_ACCEPTED, 0),
        "rejected": counts.get(RESULT_REJECTED, 0),
        "expired": counts.get(LEASE_EXPIRED, 0),
        "agreed": counts.get(VERIFICATION_AGREED, 0),
        "disagreed": counts.get(VERIFICATION_DISAGREED, 0),
        "rejections_by_kind": kinds,
        "recent": [
            {
                "event": r.event,
                "failure_kind": r.failure_kind,
                "work_unit_id": r.work_unit_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows[:limit]
        ],
    }
