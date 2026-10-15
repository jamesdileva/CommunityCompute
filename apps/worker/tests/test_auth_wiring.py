"""Sprint 20: worker main-wiring — enroll CLI, credential attach, WS token."""

import json
import threading
import time
from pathlib import Path

import httpx

import worker.main as main_mod
from worker.credentials import Credential, load_credential, save_credential
from worker.main import parse_args, run_worker
from worker.ws_client import build_ws_url


def test_ws_url_carries_token():
    assert build_ws_url("http://h:8000", "w1") == "ws://h:8000/ws/worker/w1"
    assert build_ws_url("http://h:8000", "w1", "tok") == "ws://h:8000/ws/worker/w1?token=tok"
    assert build_ws_url("https://h:443", "w1", "tok") == "wss://h:443/ws/worker/w1?token=tok"


def test_enroll_cli_saves_and_exits(tmp_path, monkeypatch):
    calls: list[dict] = []

    def fake_enroll(url, token, timeout=None, verify=True):
        calls.append({"url": url, "token": token})
        return Credential(worker_id="w-77", token="cred-77")

    monkeypatch.setattr(main_mod, "enroll_credential", fake_enroll)
    args = parse_args(["--enroll", "enroll-tok", "--worker-id-file", str(tmp_path / ".worker_id")])
    assert run_worker(args, threading.Event()) == 0
    assert calls == [{"url": "http://127.0.0.1:8000", "token": "enroll-tok"}]
    saved = json.loads((tmp_path / "credential.json").read_text(encoding="utf-8"))
    assert saved == {"worker_id": "w-77", "token": "cred-77"}


def test_enroll_cli_failure_exits_nonzero(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise httpx.HTTPStatusError("401", request=httpx.Request("POST", "http://x"),
                                    response=httpx.Response(401))

    monkeypatch.setattr(main_mod, "enroll_credential", boom)
    args = parse_args(["--enroll", "bad", "--worker-id-file", str(tmp_path / ".worker_id")])
    assert run_worker(args, threading.Event()) == 1
    assert load_credential(tmp_path / ".worker_id") is None


def test_credential_file_overrides_id_file(tmp_path, monkeypatch):
    """Enrolled worker_id wins over the locally generated UUID."""
    cred = Credential(worker_id="w-enrolled", token="t")
    save_credential(tmp_path / ".worker_id", cred)
    (tmp_path / ".worker_id").write_text("ignoreme", encoding="utf-8")
    seen: list[str] = []

    def fake_register(url, payload, timeout=None, verify=True, credential=None):
        seen.append(payload["worker_id"])
        return {"id": payload["worker_id"]}

    monkeypatch.setattr(main_mod, "register_worker", fake_register)
    args = parse_args(["--once", "--worker-id-file", str(tmp_path / ".worker_id"),
                       "--no-capabilities"])
    assert run_worker(args, threading.Event()) == 0
    assert seen == ["w-enrolled"]


def test_requests_carry_credential(tmp_path, monkeypatch):
    cred = Credential(worker_id="w-1", token="tok")
    save_credential(tmp_path / ".worker_id", cred)
    (tmp_path / ".worker_id").write_text("ignoreme", encoding="utf-8")
    got: list[Credential | None] = []

    def fake_register(url, payload, timeout=None, verify=True, credential=None):
        got.append(credential)
        return {"id": payload["worker_id"]}

    monkeypatch.setattr(main_mod, "register_worker", fake_register)
    monkeypatch.setattr(main_mod, "report_capabilities", lambda *a, **k: None)
    args = parse_args(["--once", "--worker-id-file", str(tmp_path / ".worker_id")])
    assert run_worker(args, threading.Event()) == 0
    assert got == [cred]


class _FewTicks:
    """Lets the loop run `n` iterations before reporting stopped."""

    def __init__(self, n: int) -> None:
        self.n = n

    def is_set(self) -> bool:
        return self.n <= 0

    def set(self) -> None:
        self.n = 0

    def wait(self, _seconds: float = 0.0) -> bool:
        self.n -= 1
        return False


def test_ws_thread_receives_token(tmp_path, monkeypatch):
    cred = Credential(worker_id="w-2", token="tok-2")
    save_credential(tmp_path / ".worker_id", cred)
    (tmp_path / ".worker_id").write_text("x", encoding="utf-8")
    seen: dict = {}

    def fake_ws_loop(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(main_mod, "register_worker",
                        lambda *a, **k: {"id": "w-2"})
    monkeypatch.setattr(main_mod, "report_capabilities", lambda *a, **k: None)
    monkeypatch.setattr(main_mod, "send_heartbeat",
                        lambda *a, **k: {"status": "online"})
    monkeypatch.setattr(main_mod, "report_resources", lambda *a, **k: None)
    monkeypatch.setattr(main_mod, "_availability",
                        lambda policy, ledger=None: ((True, "ok"),
                                        {"available": True, "paused": False, "reason": "ok"},
                                        {}))
    monkeypatch.setattr(main_mod, "claim_work", lambda *a, **k: None)

    stop = _FewTicks(2)  # register tick + one heartbeat/tick
    args = parse_args(["--loop", "--interval", "0.01",
                       "--heartbeat-interval", "0.05",
                       "--worker-id-file", str(tmp_path / ".worker_id")])
    assert run_worker(args, stop, ws_loop_fn=fake_ws_loop) == 0
    # background thread: give it a moment, the loop already ticked twice
    deadline = time.monotonic() + 2.0
    while "token" not in seen and time.monotonic() < deadline:
        time.sleep(0.02)
    # the ws_loop kwargs captured by our fake include the token
    assert seen.get("token") == "tok-2"


def test_no_credential_no_token(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "register_worker",
                        lambda *a, **k: {"id": "x"})
    monkeypatch.setattr(main_mod, "report_capabilities", lambda *a, **k: None)
    monkeypatch.setattr(main_mod, "send_heartbeat",
                        lambda *a, **k: {"status": "online"})
    monkeypatch.setattr(main_mod, "report_resources", lambda *a, **k: None)
    monkeypatch.setattr(main_mod, "_availability",
                        lambda policy, ledger=None: ((True, "ok"),
                                        {"available": True, "paused": False, "reason": "ok"},
                                        {}))
    monkeypatch.setattr(main_mod, "claim_work", lambda *a, **k: None)
    got: list = []
    monkeypatch.setattr(main_mod, "send_heartbeat",
                        lambda *a, **k: got.append(k.get("credential")) or {"status": "ok"})

    stop = _FewTicks(2)
    args = parse_args(["--loop", "--interval", "0.01",
                       "--heartbeat-interval", "0.05",
                       "--worker-id-file", str(tmp_path / ".worker_id")])
    assert run_worker(args, stop) == 0
    assert got == [None]
