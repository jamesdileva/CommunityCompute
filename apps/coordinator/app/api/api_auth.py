"""Auth endpoints (Sprint 20): operator minting + worker enrollment.

Worker flow:

    POST /auth/enrollment-tokens            (operator: single-use bootstrap)
    POST /auth/enroll {enrollment_token}    (worker: → worker_id + bearer credential)

The worker keeps `worker_id` + `token` in its credential file and sends
`Authorization: Bearer <token>` on every request (HTTP + WS) from then on.
`AUTH_ENABLED=false` (default) keeps the pre-Sprint-20 LAN dev flow working
while the authenticated path rolls out; setting it to true locks every
worker-facing route.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.auth import EnrollmentToken
from app.schemas.auth import (
    CredentialOut,
    EnrollRequest,
    EnrollResponse,
    EnrollmentTokenCreate,
    EnrollmentTokenInfo,
    EnrollmentTokenOut,
    RevokeResponse,
    RotateResponse,
    new_worker_id,
)
from app.services import auth as auth_service

log = logging.getLogger("coordinator")

router = APIRouter()


@router.post("/auth/enrollment-tokens", response_model=EnrollmentTokenOut, status_code=201)
def create_enrollment_token(
    payload: EnrollmentTokenCreate, db: Session = Depends(get_db)
) -> EnrollmentTokenOut:
    """Mint a single-use enrollment token (operator bootstrap)."""
    raw, row = auth_service.mint_enrollment_token(db, note=payload.note,
                                                  ttl_minutes=payload.ttl_minutes)
    log.info("enrollment token minted id=%s note=%s", row.id, payload.note)
    return EnrollmentTokenOut(token=raw, id=row.id, note=row.note,
                              expires_at=row.expires_at.isoformat() if row.expires_at else None)


@router.get("/auth/enrollment-tokens", response_model=list[EnrollmentTokenInfo])
def list_enrollment_tokens(db: Session = Depends(get_db)) -> list[EnrollmentTokenInfo]:
    rows = db.query(EnrollmentToken).order_by(EnrollmentToken.created_at.desc()).all()
    return [
        EnrollmentTokenInfo(
            id=r.id, note=r.note,
            expires_at=r.expires_at.isoformat() if r.expires_at else None,
            used=r.used_at is not None, used_by=r.used_by,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]


@router.post("/auth/enroll", response_model=EnrollResponse, status_code=201)
def enroll_worker(payload: EnrollRequest, db: Session = Depends(get_db)) -> EnrollResponse:
    """Exchange an enrollment token for a worker identity + bearer credential."""
    worker_id = new_worker_id()
    ok, reason, _credential, raw_credential = auth_service.redeem_enrollment_token(
        db, payload.enrollment_token, worker_id
    )
    if not ok:
        raise HTTPException(status_code=401,
                            detail={"error": "enroll failed", "reason": reason})
    log.info("worker enrolled id=%s", worker_id)
    return EnrollResponse(worker_id=worker_id, token=raw_credential, status="enrolled")


@router.post("/workers/{worker_id}/rotate-credential", response_model=RotateResponse)
def rotate_credential(worker_id: str, db: Session = Depends(get_db)) -> RotateResponse:
    """Issue a fresh credential; the previous one is revoked immediately."""
    ok, reason, raw = auth_service.rotate_credential(db, worker_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": reason})
    log.info("credential rotated id=%s", worker_id)
    return RotateResponse(worker_id=worker_id, token=raw or "", status="rotated")


@router.post("/workers/{worker_id}/revoke", response_model=RevokeResponse)
def revoke_worker_credentials(worker_id: str, db: Session = Depends(get_db)) -> RevokeResponse:
    """Revoke every credential for this worker (exit: a revoked worker loses access)."""
    ok, reason, count = auth_service.revoke_worker(db, worker_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": reason})
    log.info("worker revoked id=%s count=%d", worker_id, count)
    return RevokeResponse(worker_id=worker_id, revoked=count, status="revoked")


@router.get("/workers/{worker_id}/credentials", response_model=list[CredentialOut])
def list_worker_credentials(worker_id: str, db: Session = Depends(get_db)) -> list[CredentialOut]:
    """Non-secret credential view (no hashes) — operator/dashboard auditing."""
    return [CredentialOut(**r) for r in auth_service.list_credentials(db, worker_id)]


@router.get("/auth/credentials", response_model=list[CredentialOut])
def list_all_credentials(db: Session = Depends(get_db)) -> list[CredentialOut]:
    return [CredentialOut(**r) for r in auth_service.list_credentials(db)]
