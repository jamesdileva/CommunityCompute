"""Work API schemas (Sprint 6): assignment out, result in; Sprint 7 adds lease fields."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

WORKLOAD_TYPE = "hello_compute"


class WorkAssignment(BaseModel):
    """Coordinator → Worker. `payload` carries workload-specific inputs."""

    protocol_version: str
    work_unit_id: str
    job_id: str
    workload_type: str
    range_start: int
    range_end: int
    params: dict = Field(default_factory=dict)
    lease_id: str | None = None
    lease_expires_at: datetime | None = None
    attempt_number: int = 1
    # Sprint 21: HMAC seal over the unit identity + inputs. The worker
    # verifies before executing and refuses on mismatch.
    manifest_signature: str | None = None


class WorkResult(BaseModel):
    """Worker → Coordinator. Value verified against coordinator's expectation."""

    protocol_version: str = ""
    worker_id: str
    status: str = Field(pattern="^(completed|failed)$")
    value: object | None = None
    output_hash: str | None = None
    error: str | None = None
    metrics: dict = Field(default_factory=dict)  # e.g. {"execution_ms": 12.3}


class ClaimRequest(BaseModel):
    """Worker → Coordinator claim body. Empty list = no cache preference."""

    cached_models: list[str] = Field(default_factory=list)


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    work_unit_id: str
    worker_id: str | None = None
    ok: bool
    value: object | None = None
    output_hash: str | None = None
    execution_ms: float | None = None
    error: str | None = None
    failure_kind: str | None = None
    verified_by: str | None = None
    metrics: dict | None = None
    created_at: object = None
