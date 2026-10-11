"""Sprint 11: policy engine matrix (each condition trips with its reason)."""

from datetime import datetime

import pytest

from worker.policy.engine import evaluate
from worker.policy.schema import AvailabilityPolicy, ScheduleWindow
from worker.policy.state import MachineState

NOON = datetime(2026, 10, 12, 12, 0, 0)  # Monday


def _state(**over):
    base = dict(
        cpu_percent=5.0, gpu_percent=5.0, gpu_temp_c=50.0,
        on_battery=False, idle_seconds=600.0, now=NOON,
    )
    base.update(over)
    return MachineState(**base)


def test_defaults_allow_everything():
    assert evaluate(AvailabilityPolicy(), _state()) == (True, "ok")


def test_paused_wins_over_everything_else():
    policy = AvailabilityPolicy(paused=True)
    assert evaluate(policy, _state(cpu_percent=99.0)) == (False, "paused by contributor")


def test_cpu_limit_trips():
    policy = AvailabilityPolicy(max_cpu_percent=50.0)
    ok, reason = evaluate(policy, _state(cpu_percent=80.0))
    assert ok is False and "cpu" in reason
    assert evaluate(policy, _state(cpu_percent=20.0))[0] is True


def test_cpu_unknown_fails_closed():
    policy = AvailabilityPolicy(max_cpu_percent=50.0)
    ok, reason = evaluate(policy, _state(cpu_percent=None))
    assert ok is False and "unknown" in reason


def test_gpu_limit_trips():
    policy = AvailabilityPolicy(max_gpu_percent=10.0)
    assert evaluate(policy, _state(gpu_percent=80.0))[0] is False
    assert evaluate(policy, _state(gpu_percent=5.0))[0] is True


def test_temperature_ceiling_trips():
    policy = AvailabilityPolicy(temperature_ceiling_c=60.0)
    assert evaluate(policy, _state(gpu_temp_c=90.0))[0] is False
    assert evaluate(policy, _state(gpu_temp_c=50.0))[0] is True
    # undetectable temperature under a ceiling denies (never blind-run hot)
    assert evaluate(policy, _state(gpu_temp_c=None))[0] is False


def test_battery_policy():
    policy = AvailabilityPolicy(battery_policy="plugged_only")
    assert evaluate(policy, _state(on_battery=True))[0] is False
    assert evaluate(policy, _state(on_battery=False))[0] is True


def test_idle_only_with_known_idle():
    policy = AvailabilityPolicy(idle_only=True, idle_threshold_seconds=180)
    assert evaluate(policy, _state(idle_seconds=60.0))[0] is False
    assert evaluate(policy, _state(idle_seconds=600.0))[0] is True


def test_idle_only_unknown_idle_fails_closed():
    policy = AvailabilityPolicy(idle_only=True)
    assert evaluate(policy, _state(idle_seconds=None))[0] is False


def test_schedule_inside_and_outside():
    policy = AvailabilityPolicy(allowed_hours=ScheduleWindow(start_hour=9, end_hour=17))
    assert evaluate(policy, _state())[0] is True  # noon
    night = NOON.replace(hour=22)
    ok, reason = evaluate(policy, _state(now=night))
    assert ok is False and "outside allowed" in reason


def test_schedule_day_filter():
    policy = AvailabilityPolicy(
        allowed_hours=ScheduleWindow(start_hour=0, end_hour=23, days=[5])  # Saturday only
    )
    assert evaluate(policy, _state())[0] is False  # Monday
    saturday = NOON.replace(day=17)
    assert evaluate(policy, _state(now=saturday))[0] is True


def test_schedule_midnight_wrap():
    window = ScheduleWindow(start_hour=22, end_hour=2)
    policy = AvailabilityPolicy(allowed_hours=window)
    assert evaluate(policy, _state(now=NOON.replace(hour=23)))[0] is True
    assert evaluate(policy, _state(now=NOON.replace(hour=1)))[0] is True
    assert evaluate(policy, _state(now=NOON.replace(hour=12)))[0] is False


def test_ordering_paused_beats_cpu():
    policy = AvailabilityPolicy(paused=True, max_cpu_percent=0.0)
    assert evaluate(policy, _state(cpu_percent=100.0))[1] == "paused by contributor"


@pytest.mark.parametrize("cond,kwargs", [
    ("cpu", {"max_cpu_percent": 10.0}),
    ("gpu", {"max_gpu_percent": 10.0}),
    ("temp", {"temperature_ceiling_c": 10.0}),
])
def test_each_denial_has_a_reason(cond, kwargs):
    policy = AvailabilityPolicy(**kwargs)
    state = _state(cpu_percent=99.0, gpu_percent=99.0, gpu_temp_c=99.0)
    ok, reason = evaluate(policy, state)
    assert ok is False
    assert reason and reason != "ok"
