"""Customer API schemas (Sprint 29).

The customer-facing request is deliberately *separate* from ``JobCreate``:
a customer may set workload/params/requirements but can never name a worker
submitter or another customer. Ownership always comes from the API key.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.job import Requirements
from app.services.workloads import is_known_workload


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    label: str | None = Field(default=None, max_length=128)  # first key's label


class CustomerCreated(BaseModel):
    """Returned once at creation. `api_key` is the only time the raw key is shown."""

    id: str
    name: str
    api_key: str


class MeOut(BaseModel):
    """Identity of the authenticated customer (Sprint 30)."""

    customer_id: str
    name: str
    status: str


class JobSummary(BaseModel):
    """Customer-owned job listing row (Sprint 30)."""

    id: str
    workload_type: str
    status: str
    total_units: int
    created_at: object = None


class WorkloadManifestOut(BaseModel):
    """A signed workload definition (Sprint 30) served for discovery."""

    name: str
    version: str
    description: str = ""
    params: dict = Field(default_factory=dict)
    requirements: dict = Field(default_factory=dict)
    deterministic: bool = True
    signature: str


class QuotaOut(BaseModel):
    """Effective per-customer caps + current usage (Sprint 30)."""

    max_units_per_job: int
    max_in_flight_jobs: int
    max_units_in_flight: int
    in_flight_jobs: int
    units_in_flight: int


class CustomerOut(BaseModel):
    id: str
    name: str
    status: str
    active_keys: int
    created_at: str | None


class CustomerKeyOut(BaseModel):
    id: str
    customer_id: str
    prefix: str
    label: str | None
    status: str
    created_at: str | None
    last_seen: str | None
    revoked_at: str | None


class RotateKeyResponse(BaseModel):
    customer_id: str
    api_key: str  # new key; the previous one stops working immediately
    status: str


class RevokeCustomerResponse(BaseModel):
    customer_id: str
    revoked: int
    status: str


class CustomerJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workload_type: str = Field(min_length=1, max_length=64)
    params: dict = Field(default_factory=dict)
    total_units: int = Field(gt=0)
    chunk_size: int = Field(gt=0)
    verify_sample: float = Field(default=0.0, ge=0.0, le=1.0)
    requirements: Requirements = Field(default_factory=Requirements)

    @field_validator("workload_type")
    @classmethod
    def _allowlisted_type(cls, value: str) -> str:
        # Same allowlist gate as the dashboard route (Sprint 21): unknown
        # workload types fail at submit, before any worker could see them.
        if not is_known_workload(value):
            raise ValueError(f"unknown workload type {value!r} (not allowlisted)")
        return value


class JobAccepted(BaseModel):
    id: str
    status: str
    workload_type: str
    total_units: int


class JobResultUnit(BaseModel):
    work_unit_id: str
    sequence: int
    range_start: int
    range_end: int
    status: str
    ok: bool | None = None
    value: object = None
    output_hash: str | None = None
    execution_ms: float | None = None
    verified_by: str | None = None
    failure_kind: str | None = None


class JobResultsOut(BaseModel):
    job_id: str
    status: str
    total_units: int
    counts: dict[str, int] = Field(default_factory=dict)
    aggregate: dict | None = None
    results: list[JobResultUnit] = Field(default_factory=list)


class UsageOut(BaseModel):
    customer_id: str
    jobs: int
    units: int
    units_by_status: dict[str, int] = Field(default_factory=dict)
    units_by_workload: dict[str, int] = Field(default_factory=dict)
