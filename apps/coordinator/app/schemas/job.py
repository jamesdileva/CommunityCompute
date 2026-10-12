"""Job API schemas (Sprint 5)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import CANCELLED, COMPLETED, FAILED, QUEUED, RUNNING

JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
WorkUnitStatus = Literal[
    "queued", "dispatched", "running", "completed", "failed", "cancelled", "interrupted"
]


class Requirements(BaseModel):
    """Declarative workload requirements (Sprint 9, implementation-guide §10).

    Unknown keys are rejected (extra="forbid") so typos fail loudly at
    submit time instead of silently never matching.
    """

    model_config = ConfigDict(extra="forbid")

    cpu_cores: int | None = Field(default=None, ge=0)
    ram_mb: int | None = Field(default=None, ge=0)
    gpu: bool = False
    gpu_vendor: str | None = Field(default=None, max_length=32)
    min_vram_mb: int | None = Field(default=None, ge=0)
    os: str | None = Field(default=None, max_length=64)
    runtime: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=128)  # Sprint 15: cache affinity


class JobCreate(BaseModel):
    workload_type: str = Field(min_length=1, max_length=64)
    params: dict = Field(default_factory=dict)
    total_units: int = Field(gt=0)
    chunk_size: int = Field(gt=0)
    verify_sample: float = Field(default=0.0, ge=0.0, le=1.0)
    requirements: Requirements = Field(default_factory=Requirements)


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
    verify_sample: float = 0.0
    requirements: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobStatusOut(JobOut):
    """Job detail + progress aggregates + its work units."""

    work_units: list[WorkUnitOut] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    aggregate: dict | None = None
