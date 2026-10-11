"""Resource sample schemas (Sprint 12)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResourceReport(BaseModel):
    """Worker → Coordinator telemetry sample. All fields optional (undetectable)."""

    cpu_percent: float | None = None
    ram_available_mb: int | None = None
    ram_used_percent: float | None = None
    gpu_percent: float | None = None
    gpu_vram_used_mb: int | None = None
    gpu_temp_c: float | None = None


class SampleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    worker_id: str
    sampled_at: datetime | None = None
    cpu_percent: float | None = None
    ram_available_mb: int | None = None
    ram_used_percent: float | None = None
    gpu_percent: float | None = None
    gpu_vram_used_mb: int | None = None
    gpu_temp_c: float | None = None
