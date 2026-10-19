"""Data retention (Sprint 35): the single, testable deletion path.

The prototype accumulates append-only telemetry and per-unit artifacts that
grow without bound. This module enforces the documented retention policy (see
`docs/data-retention.md`). It is **never run automatically**: an operator
invokes it explicitly via `POST /beta/prune` or `scripts/prune.py`, both of
which default to a dry run.

Three windows, all independent:

- **telemetry** (`telemetry_days`): worker heartbeats + resource samples.
  High-write diagnostics; safe to age out quickly.
- **work** (`work_days`): terminal work units plus their results and attempt
  rows, and used/expired enrollment tokens. Only *terminal* units are eligible
  -- a unit holding a live lease (`dispatched`/`running`) or still `queued` is
  never touched.
- **financial** (`financial_days`): contribution records + the credit ledger.
  `0` means keep forever (the default -- these are the audit/economics record).

Identity (workers, credentials), job summaries, and reputation events are
retained: they are small and needed for trust/scheduling. Deleting unit
artifacts cannot break the ledger because neither `contribution_records` nor
`credit_ledger` has a foreign key to `work_units`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.accounting import ContributionRecord
from app.models.attempt import WorkUnitAttempt
from app.models.auth import EnrollmentToken
from app.models.credit import CreditEntry
from app.models.heartbeat import WorkerHeartbeat
from app.models.result import Result
from app.models.sample import ResourceSample
from app.models.work_unit import (
    CANCELLED,
    COMPLETED,
    FAILED,
    INTERRUPTED,
    WorkUnit,
)

TERMINAL_STATUSES = (COMPLETED, FAILED, CANCELLED, INTERRUPTED)


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _cutoff(days: int | None, now: datetime) -> datetime | None:
    """A naive UTC timestamp before which rows are stale (None = window off).

    SQLite stores naive datetimes, so comparisons strip tzinfo (same convention
    as `services/availability.py` / `accounting.availability_fraction`).
    """
    if days is None or days <= 0:
        return None
    return (now - timedelta(days=days)).replace(tzinfo=None)


def _count_or_delete(db: Session, model, condition, apply: bool) -> int:
    query = db.query(model).filter(condition)
    if not apply:
        return db.query(func.count()).select_from(model).filter(condition).scalar() or 0
    return query.delete(synchronize_session=False)


def _terminal_unit_ids(db: Session, cutoff: datetime) -> list[str]:
    rows = (
        db.query(WorkUnit.id)
        .filter(
            WorkUnit.status.in_(TERMINAL_STATUSES),
            func.coalesce(WorkUnit.updated_at, WorkUnit.created_at) < cutoff,
        )
        .all()
    )
    return [row[0] for row in rows]


def prune(
    db: Session,
    *,
    telemetry_days: int = 7,
    work_days: int = 30,
    financial_days: int = 0,
    now: datetime | None = None,
    apply: bool = False,
) -> dict:
    """Delete rows older than each window. Returns a per-table count report.

    `apply=False` (the default) is a dry run: it counts without deleting.
    Windows <= 0 disable that category entirely.
    """
    moment = _now(now)
    naive_now = moment.replace(tzinfo=None)
    deleted: dict[str, int] = {}

    telemetry_cutoff = _cutoff(telemetry_days, moment)
    if telemetry_cutoff is not None:
        deleted["worker_heartbeats"] = _count_or_delete(
            db, WorkerHeartbeat, WorkerHeartbeat.received_at < telemetry_cutoff, apply
        )
        deleted["worker_resource_samples"] = _count_or_delete(
            db, ResourceSample, ResourceSample.sampled_at < telemetry_cutoff, apply
        )

    work_cutoff = _cutoff(work_days, moment)
    if work_cutoff is not None:
        unit_ids = _terminal_unit_ids(db, work_cutoff)
        deleted["work_units"] = len(unit_ids)
        if apply and unit_ids:
            db.query(Result).filter(Result.work_unit_id.in_(unit_ids)).delete(
                synchronize_session=False
            )
            db.query(WorkUnitAttempt).filter(
                WorkUnitAttempt.work_unit_id.in_(unit_ids)
            ).delete(synchronize_session=False)
            db.query(WorkUnit).filter(WorkUnit.id.in_(unit_ids)).delete(
                synchronize_session=False
            )
        deleted["enrollment_tokens"] = _count_or_delete(
            db,
            EnrollmentToken,
            and_(
                EnrollmentToken.created_at < work_cutoff,
                or_(
                    EnrollmentToken.used_at.is_not(None),
                    EnrollmentToken.expires_at < naive_now,
                ),
            ),
            apply,
        )

    financial_cutoff = _cutoff(financial_days, moment)
    if financial_cutoff is not None:
        deleted["contribution_records"] = _count_or_delete(
            db, ContributionRecord, ContributionRecord.created_at < financial_cutoff, apply
        )
        deleted["credit_ledger"] = _count_or_delete(
            db, CreditEntry, CreditEntry.created_at < financial_cutoff, apply
        )
    else:
        deleted["contribution_records"] = 0
        deleted["credit_ledger"] = 0

    if apply:
        db.commit()
        db.expire_all()  # drop stale identity-map rows so callers see the deletes

    return {
        "applied": apply,
        "as_of": moment.isoformat(),
        "windows": {
            "telemetry_days": telemetry_days,
            "work_days": work_days,
            "financial_days": financial_days,
        },
        "deleted": deleted,
        "retained": ["workers", "credentials", "jobs", "reputation_events"],
    }
