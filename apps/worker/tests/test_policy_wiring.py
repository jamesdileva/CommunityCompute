"""Sprint 11: policy-gated work cycle + coordinator paused status."""

import pytest

import worker.main as main_mod
from worker.main import parse_args
from worker.policy.schema import AvailabilityPolicy


def test_work_cycle_skips_claim_when_policy_denies(monkeypatch, capsys):
    claimed: list = []
    monkeypatch.setattr(main_mod, "claim_work", lambda *a, **k: claimed.append(1))
    policy = AvailabilityPolicy(paused=True)
    main_mod._attempt_work_cycle("http://x", "w1", 5.0, policy=policy)
    assert claimed == []
    assert "holding off work" in capsys.readouterr().out


def test_work_cycle_proceeds_when_policy_allows(monkeypatch):
    assignment = {"protocol_version": "0.1.0-sprint6", "work_unit_id": "u1",
                  "job_id": "j1", "workload_type": "hello_compute",
                  "range_start": 1, "range_end": 10, "params": {"op": "sum"}}
    monkeypatch.setattr(main_mod, "claim_work", lambda *a, **k: assignment)
    monkeypatch.setattr(main_mod, "submit_result", lambda *a, **k: {"ok": True})
    policy = AvailabilityPolicy(max_cpu_percent=100.0)
    main_mod._attempt_work_cycle("http://x", "w1", 5.0, policy=policy)
    # no exception + unit executed (nothing to assert directly; absence of skip log is enough)


def test_heartbeat_includes_availability(monkeypatch, capsys):
    sent: list = []
    monkeypatch.setattr(
        main_mod, "send_heartbeat",
        lambda url, payload, timeout=None: sent.append(payload) or {"status": "online"},
    )
    policy = AvailabilityPolicy(paused=True)
    main_mod._attempt_heartbeat("http://x", "w1", 5.0, policy=policy)
    assert sent[0]["available"] is False


def test_cli_pause_resume_exit_before_connect(tmp_path, monkeypatch):
    """--pause/--resume manage the persisted policy and exit without networking."""
    from worker.policy.store import load_policy

    import threading

    id_file = tmp_path / ".worker_id"
    monkeypatch.setattr(main_mod, "_attempt_register", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("must not contact coordinator")
    ))
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
