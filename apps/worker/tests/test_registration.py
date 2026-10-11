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
    args = parse_args(["--once", "--worker-id-file", str(tmp_path / "wid")])
    assert run_worker(args, threading.Event()) == 0


def test_run_once_failure_exits_nonzero(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(main_mod, "register_worker", boom)
    args = parse_args(["--once", "--worker-id-file", str(tmp_path / "wid")])
    assert run_worker(args, threading.Event()) == 1


def test_run_loop_stops_when_event_set(monkeypatch, tmp_path):
    calls: list = []
    monkeypatch.setattr(main_mod, "register_worker",
                        lambda *a, **k: calls.append(1) or {"id": "ok"})
    stop = threading.Event()
    stop.set()  # shutdown requested before first iteration
    args = parse_args(["--loop", "--interval", "0.01",
                       "--worker-id-file", str(tmp_path / "wid")])
    assert run_worker(args, stop) == 0
    assert calls == []
