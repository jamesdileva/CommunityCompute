"""Capability schemas (Sprint 3).

Server-side contract for worker-reported profiles. `extra="forbid"` makes
the coordinator reject unknown/typo'd fields (fail closed, 422) instead of
silently storing junk.
"""

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1"


class CPUInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arch: str | None = None
    processor: str | None = None
    logical_cores: int | None = None
    physical_cores: int | None = None
    freq_mhz: float | None = None


class MemoryInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_mb: int | None = None
    available_mb: int | None = None


class OSInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str | None = None
    release: str | None = None
    version: str | None = None


class GPUInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: str = "unknown"
    model: str = "unknown"
    vram_mb: int | None = None
    driver: str | None = None
    utilization_percent: float | None = None
    source: str = "unknown"


class CapabilityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    cpu: CPUInfo = Field(default_factory=CPUInfo)
    ram: MemoryInfo = Field(default_factory=MemoryInfo)
    os: OSInfo = Field(default_factory=OSInfo)
    gpus: list[GPUInfo] = Field(default_factory=list)
    runtimes: list[str] = Field(default_factory=list)  # Sprint 9: executable workloads
    cached_models: list[dict] = Field(default_factory=list)  # Sprint 15: {name, version}
