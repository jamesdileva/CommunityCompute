"""Sprint 2: registration payload, client, and run outcomes (network mocked)."""

import socket
import threading

import httpx
import pytest

import worker.main as main_mod
from worker import __version__ as WORKER_VERSION
from worker.main import parse_args, run_worker
from worker.registration import build_payload, register_worker


def test_build_payload_defaults():
    payload = build_payload("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert payload == {
        "worker_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "worker_version": WORKER_VERSION,
        "hostname": socket.gethostname(),
    }


def test_register_worker_ok(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        assert url.endswith("/workers/register")
        assert json["worker_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"id": json["worker_id"], "status": "online"},
                              request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    result = register_worker("http://127.0.0.1:8000",
                             build_payload("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    assert result["status"] == "online"


def test_register_worker_failure_raises(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(httpx.ConnectError):
        register_worker("http://127.0.0.1:8000", build_payload("x"))


def test_run_once_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(main_mod, "register_worker",
                        lambda *a, **k: {"id": "ok", "status": "online"})
    monkeypatch.setattr(main_mod, "_attempt_report_capabilities", lambda *a, **k: None)
    args = parse_args(["--once", "--worker-id-file", str(tmp_path / "wid")])
    assert run_worker(args, threading.Event()) == 0


def test_run_once_ok_without_capability_report(monkeypatch, tmp_path):
    """Telemetry failure must not fail a successful registration (telemetry only)."""
    monkeypatch.setattr(main_mod, "register_worker",
                        lambda *a, **k: {"id": "ok", "status": "online"})

    def boom(*a, **k):
        raise httpx.ConnectError("refused")

    # patch the inner client (discovery stays real; the wrapper must swallow this)
    monkeypatch.setattr(main_mod, "report_capabilities", boom)
    args = parse_args(["--once", "--worker-id-file", str(tmp_path / "wid")])
    assert run_worker(args, threading.Event()) == 0


def test_run_once_failure_exits_nonzero(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(main_mod, "register_worker", boom)
    monkeypatch.setattr(main_mod, "_attempt_report_capabilities", lambda *a, **k: None)
    args = parse_args(["--once", "--worker-id-file", str(tmp_path / "wid")])
    assert run_worker(args, threading.Event()) == 1


def test_run_loop_stops_when_event_set(monkeypatch, tmp_path):
    calls: list = []
    monkeypatch.setattr(main_mod, "register_worker",
                        lambda *a, **k: calls.append(1) or {"id": "ok"})
    monkeypatch.setattr(main_mod, "_attempt_report_capabilities", lambda *a, **k: None)
    stop = threading.Event()
    stop.set()  # shutdown requested before first iteration
    args = parse_args(["--loop", "--interval", "0.01",
                       "--worker-id-file", str(tmp_path / "wid")])
    assert run_worker(args, stop) == 0
    assert calls == []


def test_run_loop_registers_once_then_ticks(monkeypatch, tmp_path):
    """Sprint 12 cadence: register once (immediate heartbeat), then per-tick
    telemetry + policy + work, with heartbeats on their own (slower) cadence."""
    events: list[str] = []
    monkeypatch.setattr(
        main_mod, "register_worker",
        lambda *a, **k: events.append("register") or {"id": "ok"},
    )
    monkeypatch.setattr(main_mod, "report_capabilities",
                        lambda *a, **k: events.append("capabilities"))
    monkeypatch.setattr(main_mod, "send_heartbeat",
                        lambda *a, **k: events.append("heartbeat") or {"status": "online"})
    monkeypatch.setattr(main_mod, "report_resources",
                        lambda *a, **k: events.append("resources"))
    monkeypatch.setattr(main_mod, "_availability",
                        lambda policy: ((True, "ok"),
                                        {"available": True, "paused": False, "reason": "ok"},
                                        {"cpu_percent": 1.0}))
    monkeypatch.setattr(main_mod, "claim_work", lambda *a, **k: None)  # idle queue

    class OneShotEvent:
        """Sets after 3 waits → exits the loop after 2 more ticks."""

        def __init__(self) -> None:
            self._waits = 0

        def is_set(self) -> bool:
            return self._waits >= 3

        def set(self) -> None:
            self._waits = 99

        def wait(self, _seconds: float) -> bool:
            self._waits += 1
            return False

    args = parse_args(["--loop", "--interval", "0.01", "--heartbeat-interval", "0.02",
                       "--worker-id-file", str(tmp_path / "wid")])
    assert run_worker(args, OneShotEvent()) == 0  # type: ignore[arg-type]
    assert events.count("register") == 1  # registration happens once
    assert events.count("capabilities") == 1
    assert events.count("heartbeat") >= 1
    assert events.count("resources") == 2  # telemetry every tick
    assert events[:2] == ["register", "capabilities"]
