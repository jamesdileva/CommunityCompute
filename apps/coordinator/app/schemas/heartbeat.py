"""Heartbeat schemas (Sprint 4).

Heartbeat proves liveness; the coordinator derives online/offline from
`last_seen` vs a configured timeout — the worker never declares itself
"online" authoritatively.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResourceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    ram_available_mb: int | None = Field(default=None, ge=0)
    gpu_percent: float | None = Field(default=None, ge=0, le=100)


class Heartbeat(BaseModel):
    worker_id: UUID
    resources: ResourceSnapshot = Field(default_factory=ResourceSnapshot)


class HeartbeatResponse(BaseModel):
    status: str
    server_time: str
