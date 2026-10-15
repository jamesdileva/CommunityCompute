"""Policy engine (Sprint 11): ordered evaluation with an explanation.

Order = cheapest and most decisive first. Any condition that trips denies
availability with a human-readable reason. Unknown signals (None) are
fail-closed where safety demands it: an *undetectable* idle time under
`idle_only` denies (we can't prove the user is idle), while an undetectable
GPU temperature under a ceiling also denies rather than blind-runs hot.
"""

from __future__ import annotations

from worker.policy.schema import BATTERY_PLUGGED_ONLY, AvailabilityPolicy
from worker.policy.state import MachineState


def evaluate(policy: AvailabilityPolicy, state: MachineState,
             bandwidth_ledger=None) -> tuple[bool, str]:
    """(available, reason). Reason is "ok" when available."""
    if policy.paused:
        return False, "paused by contributor"

    if policy.allowed_hours is not None:
        ok, why = _schedule_ok(policy.allowed_hours, state.now)
        if not ok:
            return False, why

    if policy.battery_policy == BATTERY_PLUGGED_ONLY and state.on_battery:
        return False, "running on battery (policy: plugged_only)"

    if policy.max_cpu_percent is not None:
        if state.cpu_percent is None:
            return False, "cpu usage unknown; cannot enforce limit"
        if state.cpu_percent > policy.max_cpu_percent:
            return False, (
                f"cpu {state.cpu_percent}% > limit {policy.max_cpu_percent}%"
            )

    if policy.max_gpu_percent is not None:
        if state.gpu_percent is None:
            return False, "gpu usage unknown; cannot enforce limit"
        if state.gpu_percent > policy.max_gpu_percent:
            return False, (
                f"gpu {state.gpu_percent}% > limit {policy.max_gpu_percent}%"
            )

    if policy.temperature_ceiling_c is not None:
        if state.gpu_temp_c is None:
            return False, "temperature unknown; cannot enforce ceiling"
        if state.gpu_temp_c > policy.temperature_ceiling_c:
            return False, (
                f"gpu {state.gpu_temp_c}C > ceiling {policy.temperature_ceiling_c}C"
            )

    if policy.idle_only:
        if state.idle_seconds is None:
            return False, "idle time undetectable on this platform"
        if state.idle_seconds < policy.idle_threshold_seconds:
            return False, (
                f"user active {state.idle_seconds:.0f}s < "
                f"{policy.idle_threshold_seconds}s"
            )

    if bandwidth_ledger is not None and policy.bandwidth_mbps is not None:
        if bandwidth_ledger.over_budget(policy.bandwidth_mbps):
            return False, (
                f"upload cap reached ({policy.bandwidth_mbps} Mbps per 60s window)"
            )

    return True, "ok"


def _schedule_ok(window, now) -> tuple[bool, str]:
    """Inclusive hour window (may wrap midnight); day list uses 0=Monday."""
    if window.days and now.weekday() not in window.days:
        return False, f"day {now.weekday()} not in allowed days {window.days}"
    if window.start_hour <= window.end_hour:  # same-day window
        inside = window.start_hour <= now.hour <= window.end_hour
    else:  # wraps midnight (e.g. 22 -> 2)
        inside = now.hour >= window.start_hour or now.hour <= window.end_hour
    if inside:
        return True, "ok"
    return False, (
        f"hour {now.hour} outside allowed {window.start_hour}-{window.end_hour}"
    )
