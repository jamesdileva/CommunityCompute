"""Policy schema (Sprint 11): contributor-defined availability constraints.

Guiding split (implementation-guide §18): this schema answers *"should I
accept work?"* (scheduling availability). Execution limits (how much of my
resources work may consume) are a separate, later concern.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

BATTERY_ALLOW = "allow"
BATTERY_PLUGGED_ONLY = "plugged_only"


class ScheduleWindow(BaseModel):
    """Allowed hours/days, local machine time. Empty days list = all days."""

    model_config = ConfigDict(extra="forbid")

    start_hour: int = Field(default=0, ge=0, le=23)
    end_hour: int = Field(default=23, ge=0, le=23)  # inclusive hour range
    days: list[int] = Field(default_factory=list)  # 0=Mon..6=Sun; empty = every day


class AvailabilityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paused: bool = False  # hard stop: immediate, survives restarts
    idle_only: bool = False  # contribute only when the user is idle
    idle_threshold_seconds: int = Field(default=180, ge=0)
    max_cpu_percent: float | None = Field(default=None, ge=0, le=100)
    max_gpu_percent: float | None = Field(default=None, ge=0, le=100)
    temperature_ceiling_c: float | None = Field(default=None, ge=0)
    battery_policy: str = Field(default=BATTERY_ALLOW)  # allow | plugged_only
    allowed_hours: ScheduleWindow | None = None
    # Sprint 25: rolling upload cap (MB per 60s window, claim+result payloads).
    # Prototype payloads are KB-scale, so the mechanism (account + throttle)
    # is what this proves; the number matters once artifacts grow (S15+).
    bandwidth_mbps: float | None = Field(default=None, gt=0)
