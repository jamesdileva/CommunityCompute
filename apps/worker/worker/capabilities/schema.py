"""Capability profile schema (Sprint 3).

Mirrors architecture §6 fields relevant to scheduling: hardware (CPU/RAM/GPU),
software (OS), plus a schema_version so the payload can evolve safely.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1"


class CPUInfo(BaseModel):
    arch: str | None = None
    processor: str | None = None
    logical_cores: int | None = None
    physical_cores: int | None = None
    freq_mhz: float | None = None


class MemoryInfo(BaseModel):
    total_mb: int | None = None
    available_mb: int | None = None


class OSInfo(BaseModel):
    system: str | None = None
    release: str | None = None
    version: str | None = None


class GPUInfo(BaseModel):
    vendor: str = "unknown"
    model: str = "unknown"
    vram_mb: int | None = None
    driver: str | None = None
    utilization_percent: float | None = None
    source: str = "unknown"


class CapabilityProfile(BaseModel):
    """Auto-discovered profile. `schema_version` guards payload evolution."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    cpu: CPUInfo = Field(default_factory=CPUInfo)
    ram: MemoryInfo = Field(default_factory=MemoryInfo)
    os: OSInfo = Field(default_factory=OSInfo)
    gpus: list[GPUInfo] = Field(default_factory=list)
    runtimes: list[str] = Field(default_factory=list)  # executable workload types (Sprint 9)
