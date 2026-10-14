"""Auth schemas (Sprint 20)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class EnrollmentTokenCreate(BaseModel):
    note: str | None = Field(default=None, max_length=255)
    ttl_minutes: int | None = Field(default=None, gt=0)


class EnrollmentTokenOut(BaseModel):
    """Returned once at mint. `token` is the only time the raw value is shown."""

    token: str
    id: str
    note: str | None
    expires_at: str | None


class EnrollmentTokenInfo(BaseModel):
    id: str
    note: str | None
    expires_at: str | None
    used: bool
    used_by: str | None
    created_at: str | None


class EnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enrollment_token: str = Field(min_length=8)


class EnrollResponse(BaseModel):
    worker_id: str
    token: str  # the worker's long-lived bearer credential (shown once)
    status: str


class CredentialOut(BaseModel):
    id: str
    worker_id: str
    status: str
    created_at: str | None
    last_seen: str | None
    revoked_at: str | None


class RotateResponse(BaseModel):
    worker_id: str
    token: str  # new credential; the old one stops working immediately
    status: str


class RevokeResponse(BaseModel):
    worker_id: str
    revoked: int
    status: str


def new_worker_id() -> str:
    """Coordinator-issued worker id (uuid4) — identity stays server-minted."""
    return str(uuid.uuid4())
