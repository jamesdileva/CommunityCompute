"""Sprint 11/12: policy-gated work cycle + availability payloads."""

import threading

import worker.main as main_mod
from worker.main import parse_args
from worker.policy.schema import AvailabilityPolicy


def test_work_cycle_skips_claim_when_gate_denies(monkeypatch, capsys):
    claimed: list = []
    monkeypatch.setattr(main_mod, "claim_work", lambda *a, **k: claimed.append(1))
    main_mod._attempt_work_cycle("http://x", "w1", 5.0,
                                 availability=(False, "paused by contributor"))
    assert claimed == []
    assert "holding off work: paused by contributor" in capsys.readouterr().out


def test_work_cycle_proceeds_when_gate_allows(monkeypatch):
    assignment = {"protocol_version": "0.1.0-sprint6", "work_unit_id": "u1",
                  "job_id": "j1", "workload_type": "hello_compute",
                  "range_start": 1, "range_end": 10, "params": {"op": "sum"}}
    monkeypatch.setattr(main_mod, "claim_work", lambda *a, **k: assignment)
    monkeypatch.setattr(main_mod, "submit_result", lambda *a, **k: {"ok": True})
    main_mod._attempt_work_cycle("http://x", "w1", 5.0, availability=(True, "ok"))


def test_work_cycle_no_gate_still_claims(monkeypatch):
    assignment = {"protocol_version": "0.1.0-sprint6", "work_unit_id": "u1",
                  "job_id": "j1", "workload_type": "hello_compute",
                  "range_start": 1, "range_end": 10, "params": {"op": "sum"}}
    monkeypatch.setattr(main_mod, "claim_work", lambda *a, **k: assignment)
    monkeypatch.setattr(main_mod, "submit_result", lambda *a, **k: {"ok": True})
    main_mod._attempt_work_cycle("http://x", "w1", 5.0)  # no policy at all


def test_heartbeat_carries_structured_availability(monkeypatch):
    sent: list = []
    monkeypatch.setattr(
        main_mod, "send_heartbeat",
        lambda url, payload, timeout=None: sent.append(payload) or {"status": "online"},
    )
    main_mod._attempt_heartbeat("http://x", "w1", 5.0, availability={
        "available": False, "paused": False, "reason": "cpu 95% > limit 10%",
    })
    assert sent[0]["availability"] == {
        "available": False, "paused": False, "reason": "cpu 95% > limit 10%",
    }


def test_availability_payload_shape_from_sampling(monkeypatch):
    """_availability returns verdict + payload + telemetry report in one pass."""

    class FakeState:
        cpu_percent = 12.0
        gpu_percent = None
        gpu_temp_c = None
        gpu_vram_used_mb = None
        on_battery = None
        idle_seconds = 9999.0

    monkeypatch.setattr(main_mod, "collect_state", lambda: FakeState())
    (available, reason), payload, report = main_mod._availability(AvailabilityPolicy())
    assert available is True and reason == "ok"
    assert payload == {"available": True, "paused": False, "reason": "ok"}
    assert report["cpu_percent"] == 12.0


def test_availability_denied_payload_carries_reason(monkeypatch):
    class FakeState:
        cpu_percent = 99.0
        gpu_percent = 99.0
        gpu_temp_c = 99.0
        gpu_vram_used_mb = 1.0
        on_battery = False  # plugged in → the CPU limit is what trips
        idle_seconds = 0.0

    monkeypatch.setattr(main_mod, "collect_state", lambda: FakeState())
    policy = AvailabilityPolicy(max_cpu_percent=10.0)
    (available, reason), payload, _report = main_mod._availability(policy)
    assert available is False
    assert "cpu" in reason
    assert payload == {"available": False, "paused": False, "reason": reason}


def test_cli_pause_resume_exit_before_connect(tmp_path, monkeypatch):
    """--pause/--resume manage the persisted policy and exit without networking."""
    from worker.policy.store import load_policy

    id_file = tmp_path / ".worker_id"
    monkeypatch.setattr(
        main_mod, "_attempt_register",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not contact coordinator")),
    )
    args = parse_args(["--pause", "--worker-id-file", str(id_file)])
    assert main_mod.run_worker(args, threading.Event()) == 0
    assert load_policy(main_mod._policy_file(args)).paused is True

    args = parse_args(["--resume", "--worker-id-file", str(id_file)])
    assert main_mod.run_worker(args, threading.Event()) == 0
    assert load_policy(main_mod._policy_file(args)).paused is False


def test_local_policy_file_flag(tmp_path):
    custom = tmp_path / "custom.json"
    args = parse_args(["--loop", "--policy-file", str(custom),
                       "--worker-id-file", str(tmp_path / ".worker_id")])
    assert main_mod._policy_file(args) == custom


def test_heartbeat_interval_flag_defaults():
    args = parse_args(["--loop"])
    assert args.heartbeat_interval == 20.0
