"""Worker API schemas (Sprint 2: registration; capabilities in schemas/capability.py)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkerRegistration(BaseModel):
    """Registration payload. `worker_id` is client-generated persistent UUID (never hostname)."""

    worker_id: UUID
    worker_version: str = Field(min_length=1, max_length=32)
    hostname: str | None = Field(default=None, max_length=255)


class WorkerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    worker_version: str | None = None
    hostname: str | None = None
    status: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    capabilities: dict | None = None
