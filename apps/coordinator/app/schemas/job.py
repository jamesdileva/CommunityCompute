"""Job API schemas (Sprint 5)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import CANCELLED, COMPLETED, FAILED, QUEUED, RUNNING

JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
WorkUnitStatus = Literal[
    "queued", "dispatched", "running", "completed", "failed", "cancelled", "interrupted"
]


class JobCreate(BaseModel):
    workload_type: str = Field(min_length=1, max_length=64)
    params: dict = Field(default_factory=dict)
    total_units: int = Field(gt=0)
    chunk_size: int = Field(gt=0)


class WorkUnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    sequence: int
    range_start: int
    range_end: int
    status: WorkUnitStatus
    assigned_worker_id: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workload_type: str
    params: dict
    total_units: int
    chunk_size: int
    status: JobStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobStatusOut(JobOut):
    """Job detail + progress aggregates + its work units."""

    work_units: list[WorkUnitOut] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    aggregate: dict | None = None
