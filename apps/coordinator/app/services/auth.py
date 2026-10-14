"""Credential service (Sprint 20): hash, verify, mint, rotate, revoke.

Design rules:

- **Hash-only storage** — sha256 of the raw token; a DB leak yields no usable
  bearer tokens. No password-style slowness: these are 32-byte random values.
- **Random = `secrets.token_urlsafe(32)`** — ~256 bits, URL-safe.
- **Revocation is immediate** — `status` is checked on every authenticated
  call, so a revoked worker's claims stop on its next request.
- **Single-use enrollment** — redemption records `used_by`, so replaying the
  same enrollment token can't mint a second credential.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.auth import EnrollmentToken, WorkerCredential, _aware
from app.models.worker import Worker


def hash_token(raw: str) -> str:
    """sha256 hex of the raw token (the only form ever stored)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def mint_enrollment_token(
    db: Session, note: str | None = None, ttl_minutes: int | None = None
) -> tuple[str, EnrollmentToken]:
    """Create an enrollment token; returns (raw, row). Raw is shown once."""
    raw = _new_token()
    expires = (
        datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes) if ttl_minutes else None
    )
    row = EnrollmentToken(id=secrets.token_hex(4), token_hash=hash_token(raw), note=note,
                          expires_at=expires)
    db.add(row)
    db.commit()
    db.refresh(row)
    return raw, row


def redeem_enrollment_token(
    db: Session, raw: str, worker_id: str
) -> tuple[bool, str, WorkerCredential | None, str]:
    """Exchange an enrollment token for a worker credential.

    Returns (ok, reason, credential, raw_credential). The raw credential is
    returned alongside the row so the endpoint can hand it to the worker once
    (only hashes are persisted). The worker record is created here when the
    coordinator hasn't seen it yet.
    """
    row = db.query(EnrollmentToken).filter_by(token_hash=hash_token(raw)).first()
    if row is None:
        return False, "unknown enrollment token", None, ""
    if not row.active():
        return False, "enrollment token expired or already used", None, ""

    now = datetime.now(timezone.utc)
    row.used_at = now
    row.used_by = worker_id

    worker = db.get(Worker, worker_id)
    if worker is None:
        worker = Worker(id=worker_id, status="online", last_seen=now)
        db.add(worker)

    raw_credential = _new_token()
    credential = WorkerCredential(id=secrets.token_hex(6), worker_id=worker_id,
                                   token_hash=hash_token(raw_credential))
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return True, "enrolled", credential, raw_credential


def issue_credential(db: Session, worker_id: str) -> tuple[WorkerCredential, str]:
    """Create and return (row, raw) for an existing or pending worker."""
    raw = _new_token()
    row = WorkerCredential(id=secrets.token_hex(6), worker_id=worker_id,
                           token_hash=hash_token(raw))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw


def verify_credential(
    db: Session, raw: str, worker_id: str | None = None
) -> WorkerCredential | None:
    """Return the active credential for this raw token (refreshes last_seen).

    `worker_id`, when given, must match the credential's worker — the bearer
    token alone is never enough to act as someone else.
    """
    if not raw:
        return None
    row = (
        db.query(WorkerCredential)
        .filter(WorkerCredential.token_hash == hash_token(raw))
        .first()
    )
    if row is None or not row.is_active():
        return None
    if worker_id is not None and row.worker_id != worker_id:
        return None
    row.last_seen = datetime.now(timezone.utc)
    db.commit()
    return row


def rotate_credential(db: Session, worker_id: str) -> tuple[bool, str, str | None]:
    """Revoke the worker's active credentials and issue a fresh one."""
    now = datetime.now(timezone.utc)
    for row in (
        db.query(WorkerCredential).filter_by(worker_id=worker_id, status="active").all()
    ):
        row.status = "revoked"
        row.revoked_at = now
    _, raw = issue_credential(db, worker_id)
    db.commit()
    return True, "rotated", raw


def revoke_worker(db: Session, worker_id: str) -> tuple[bool, str, int]:
    """Revoke every credential for a worker; returns (ok, reason, count)."""
    now = datetime.now(timezone.utc)
    rows = (
        db.query(WorkerCredential).filter_by(worker_id=worker_id, status="active").all()
    )
    for row in rows:
        row.status = "revoked"
        row.revoked_at = now
    db.commit()
    return True, "revoked", len(rows)


def list_credentials(db: Session, worker_id: str | None = None) -> list[dict]:
    """Non-secret credential view (no hashes) for the operator/dashboard."""
    rows = db.query(WorkerCredential)
    if worker_id:
        rows = rows.filter_by(worker_id=worker_id)
    return [
        {
            "id": r.id,
            "worker_id": r.worker_id,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "last_seen": r.last_seen.isoformat() if r.last_seen else None,
            "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
        }
        for r in rows.order_by(WorkerCredential.created_at.desc()).all()
    ]


def _expired(row: EnrollmentToken, now: datetime) -> bool:
    return row.expires_at is not None and _aware(row.expires_at) <= now
