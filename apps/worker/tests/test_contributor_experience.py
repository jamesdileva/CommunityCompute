"""Sprint 25: capability estimate, bandwidth throttle, onboarding wizard."""

import json
from pathlib import Path

from worker.capability_estimate import (
    contribution_class,
    plain_language_summary,
    workload_fit_note,
)
from worker.capabilities.schema import CapabilityProfile
from worker.policy.bandwidth import BandwidthLedger
from worker.policy.engine import evaluate as evaluate_policy
from worker.policy.schema import AvailabilityPolicy
from worker.policy.state import MachineState
from worker.setup_wizard import _parse_hours, run_setup


PROFILE = {
    "cpu": {"logical_cores": 12, "physical_cores": 6, "arch": "AMD64"},
    "ram": {"total_mb": 16258},
    "os": {"system": "Windows", "release": "11"},
    "gpus": [{"vendor": "amd", "model": "RX 6400", "vram_mb": 4080, "driver": "x"}],
    "runtimes": ["hello_compute", "embeddings"],
    "cached_models": [],
}


def test_contribution_class_buckets():
    assert contribution_class({"gpu": "H3", "cpu": "H3", "ram": "H3"}) == "gpu-capable"
    assert contribution_class({"gpu": "H2", "cpu": "H1", "ram": "H1"}) == "gpu-capable"
    assert contribution_class({"gpu": None, "cpu": "H2", "ram": "H2"}) == "mixed"
    assert contribution_class({"gpu": "H1", "cpu": "H1", "ram": "H1"}) == "mixed"
    assert contribution_class({"gpu": None, "cpu": "H1", "ram": "H1"}) == "cpu-only"
    assert contribution_class(None) == "unknown"


def test_plain_language_summary_lines():
    tiers = {"gpu": "H1", "cpu": "H2", "ram": "H2"}
    lines = plain_language_summary(PROFILE, tiers)
    joined = "\n".join(lines)
    assert "CPU: 6 cores (mid-range)" in joined
    assert "RAM: 15.9 GB (mid-range)" in joined
    assert "GPU: amd RX 6400 4.0 GB VRAM (modest)" in joined
    assert "hello_compute, embeddings" in joined
    assert "Contribution class: mixed" in joined


def test_plain_language_summary_no_gpu():
    tiers = {"gpu": None, "cpu": "H2", "ram": "H2"}
    lines = plain_language_summary({**PROFILE, "gpus": []}, tiers)
    assert any("GPU: none detected" in line for line in lines)


def test_workload_fit_notes():
    tiers = {"gpu": "H2", "cpu": "H3", "ram": "H2"}
    for workload in ("hello_compute", "stats_range", "embeddings"):
        assert workload_fit_note(workload, tiers).startswith(f"{workload}:")
    assert "runs on any class" in workload_fit_note("hello_compute", tiers)


def test_parse_hours_accepts_and_rejects():
    assert _parse_hours("9-17") == {"start_hour": 9, "end_hour": 17, "days": []}
    assert _parse_hours("") is None
    assert _parse_hours("garbage") is None
    assert _parse_hours("25-1") is None


def _answers(values: list[str]):
    it = iter(values)

    def ask(_prompt: str = "") -> str:
        return next(it)

    return ask


def _gpu_metered() -> dict:
    """Deterministic probe: metrics are readable (e.g. nvidia-smi present)."""
    return {"utilization_gpu": 4.0, "temperature_gpu": 38.0, "memory_used_mb": 512}


def _gpu_unmetered() -> dict:
    """Deterministic probe: nothing readable (Intel/AMD without a driver tool)."""
    return {"utilization_gpu": None, "temperature_gpu": None, "memory_used_mb": None}


def test_wizard_full_onboarding_flow(tmp_path):
    out: list[str] = []
    answers = [
        "",                    # coordinator URL (default)
        "",                    # enrollment token (none)
        "",                    # idle-only (default yes)
        "",                    # max cpu (80)
        "",                    # max gpu (80)
        "",                    # temp ceiling (none)
        "",                    # battery (allow)
        "9-17",                # hours
        "",                    # bandwidth (none)
        "",                    # autostart (no)
    ]
    configured = run_setup(
        tmp_path / ".worker_id",
        input_fn=_answers(answers),
        print_fn=out.append,
        gpu_probe=_gpu_metered,
    )
    assert configured["idle_only"] is True
    assert configured["max_cpu_percent"] == 80.0
    assert configured["max_gpu_percent"] == 80.0
    assert configured["bandwidth_mbps"] is None
    assert configured["autostart"] is False
    # onboarding actually showed the scan + estimate before policy
    assert any("Hardware scan" in line for line in out)
    assert any("Contribution class:" in line for line in out)
    assert any("docs/privacy.md" in line for line in out)
    saved = json.loads((tmp_path / "policy.json").read_text(encoding="utf-8"))
    assert saved["allowed_hours"] == {"start_hour": 9, "end_hour": 17, "days": []}
    assert saved["bandwidth_mbps"] is None


def test_wizard_reports_bandwidth_cap(tmp_path):
    answers = ["http://x:8000", "tok", "y", "50", "50", "", "plugged_only", "", "10", "n"]
    configured = run_setup(tmp_path / ".worker_id",
                           input_fn=_answers(answers),
                           print_fn=lambda _line: None,
                           gpu_probe=_gpu_metered)
    assert configured["bandwidth_mbps"] == 10.0
    assert configured["battery_policy"] == "plugged_only"


def test_wizard_omits_unenforceable_gpu_limits(tmp_path):
    """A machine whose GPU can't be measured must still be allowed to contribute.

    Sprint 36: the policy engine fails closed on an unknown GPU signal, so an
    unenforceable GPU cap/temperature ceiling would leave the machine idle
    forever. The wizard drops them instead.
    """
    out: list[str] = []
    answers = [
        "http://x:8000",  # coordinator
        "tok",            # token
        "n",              # idle-only: no
        "90",             # max cpu (this one is measurable, keep it)
        "allow",          # battery
        "",               # hours
        "",               # bandwidth
        "n",              # autostart
    ]
    configured = run_setup(tmp_path / ".worker_id",
                           input_fn=_answers(answers),
                           print_fn=out.append,
                           gpu_probe=_gpu_unmetered)
    assert configured["max_cpu_percent"] == 90.0
    assert configured["max_gpu_percent"] is None
    assert configured["temperature_ceiling_c"] is None
    assert any("GPU usage is not measurable" in line for line in out)
    saved = json.loads((tmp_path / "policy.json").read_text(encoding="utf-8"))
    assert saved["max_gpu_percent"] is None
    assert saved["temperature_ceiling_c"] is None


# ---- bandwidth ledger -------------------------------------------------------


def test_ledger_under_cap_allows():
    ledger = BandwidthLedger()
    ledger.record(1024 * 1024, at=100.0)  # 1MB
    assert ledger.over_budget(10.0, at=101.0) is False


def test_ledger_over_cap_denies():
    ledger = BandwidthLedger()
    ledger.record(2 * 1024 * 1024, at=100.0)  # 2MB > 1Mbps/60s
    assert ledger.over_budget(1.0, at=101.0) is True


def test_ledger_window_rolls_over():
    ledger = BandwidthLedger()
    ledger.record(100 * 1024 * 1024, at=0.0)
    assert ledger.over_budget(1.0, at=1.0) is True
    assert ledger.over_budget(1.0, at=61.0) is False  # outside the 60s window


def test_ledger_no_cap_always_allows():
    ledger = BandwidthLedger()
    ledger.record(10**9, at=0.0)
    assert ledger.over_budget(None) is False


def test_ledger_rejects_negative_bytes():
    ledger = BandwidthLedger()
    try:
        ledger.record(-1, at=0.0)
    except ValueError:
        return
    raise AssertionError("negative byte counts must raise")


def test_engine_denies_when_over_budget():
    state = MachineState(cpu_percent=1.0, gpu_percent=1.0, gpu_temp_c=30.0,
                         on_battery=False, idle_seconds=9999.0)
    policy = AvailabilityPolicy(bandwidth_mbps=1.0)
    available, reason = evaluate_policy(policy, state, OverCap())
    assert available is False
    assert "upload cap" in reason


class OverCap:
    def over_budget(self, _cap):
        return True


def test_engine_allows_when_cap_none():
    state = MachineState(cpu_percent=1.0, gpu_percent=1.0, gpu_temp_c=30.0,
                         on_battery=False, idle_seconds=9999.0)
    available, reason = evaluate_policy(AvailabilityPolicy(), state, OverCap())
    assert available is True and reason == "ok"


# ---- policy summary in capabilities -----------------------------------------


def test_policy_summary_excludes_paused(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKER_ID_FILE", str(tmp_path / ".worker_id"))
    (tmp_path / "policy.json").write_text(json.dumps({
        "paused": True,
        "idle_only": True,
        "max_cpu_percent": 55,
        "bandwidth_mbps": 8,
    }), encoding="utf-8")
    from worker.capabilities.discover import policy_summary

    summary = policy_summary(tmp_path / ".worker_id")
    assert "paused" not in summary
    assert summary["max_cpu_percent"] == 55
    assert summary["bandwidth_mbps"] == 8


def test_capability_profile_accepts_policy_summary():
    profile = CapabilityProfile(policy_summary={"idle_only": True})
    assert profile.policy_summary == {"idle_only": True}
    assert "policy_summary" in profile.model_dump()
