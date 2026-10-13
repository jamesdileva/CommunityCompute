"""Sprint 17: worker WS client — URL building, messages, dispatch, backoff."""

import threading
import time

import worker.main as main_mod
from worker import ws_client
from worker.main import _wait_for_next_tick, parse_args
from worker.ws_client import (
    BACKOFF_CAP,
    build_heartbeat_message,
    build_hello_message,
    build_ws_url,
    dispatch_message,
    next_backoff,
)


def test_build_ws_url_http_to_ws():
    assert build_ws_url("http://127.0.0.1:8000", "abc") == "ws://127.0.0.1:8000/ws/worker/abc"


def test_build_ws_url_https_to_wss_trailing_slash():
    assert build_ws_url("https://example.test:443/", "abc") == \
        "wss://example.test:443/ws/worker/abc"


def test_build_ws_url_passthrough():
    assert build_ws_url("ws://host:8000", "abc") == "ws://host:8000/ws/worker/abc"


def test_hello_message_shape():
    assert build_hello_message("abc") == {"type": "hello", "worker_id": "abc"}


def test_heartbeat_message_shape(monkeypatch):
    monkeypatch.setattr(
        ws_client, "build_heartbeat_payload",
        lambda wid: {"worker_id": wid,
                     "resources": {"cpu_percent": 1.0, "ram_available_mb": 2,
                                   "gpu_percent": None}},
    )
    msg = build_heartbeat_message("abc", {"available": True, "paused": False,
                                          "reason": "test"})
    assert msg["type"] == "heartbeat"
    assert msg["worker_id"] == "abc"
    assert msg["resources"]["cpu_percent"] == 1.0
    assert msg["availability"]["reason"] == "test"


def test_heartbeat_message_without_availability(monkeypatch):
    monkeypatch.setattr(
        ws_client, "build_heartbeat_payload",
        lambda wid: {"worker_id": wid, "resources": {"cpu_percent": None,
                                                     "ram_available_mb": None,
                                                     "gpu_percent": None}},
    )
    assert "availability" not in build_heartbeat_message("abc")


def test_dispatch_work_available_wakes():
    event = threading.Event()
    assert dispatch_message({"type": "work_available"}, event) == "work_available"
    assert event.is_set()


def test_dispatch_work_available_without_event():
    assert dispatch_message({"type": "work_available"}) == "work_available"


def test_dispatch_pause_resume_logged(capsys):
    assert dispatch_message({"type": "pause"}) == "pause"
    assert "paused by operator" in capsys.readouterr().out
    assert dispatch_message({"type": "resume"}) == "resume"
    assert "resumed by operator" in capsys.readouterr().out


def test_dispatch_acks_and_unknown():
    assert dispatch_message({"type": "hello_ack"}) == "hello_ack"
    assert dispatch_message({"type": "heartbeat_ack"}) == "heartbeat_ack"
    assert dispatch_message({"type": "error"}) == "error"
    assert dispatch_message({"type": "bogus"}) == "unknown"
    assert dispatch_message({}) == "unknown"


def test_backoff_doubles_then_caps():
    assert next_backoff(1.0) == 2.0
    assert next_backoff(4.0) == 8.0
    assert next_backoff(8.0) == BACKOFF_CAP
    assert next_backoff(100.0) == BACKOFF_CAP


def test_ws_loop_survives_hello_rejection(monkeypatch, tmp_path):
    """The socket can connect before HTTP registration lands (server 4404s the
    hello). That must reconnect, never kill the background thread."""
    import json as _json

    import websockets.sync.client as _sync_client
    from websockets.exceptions import ConnectionClosedError
    from websockets.frames import Close

    attempts: list[str] = []
    stop, connected, wake = threading.Event(), threading.Event(), threading.Event()

    class FakeWS:
        def __init__(self, round_no: int) -> None:
            self._round = round_no

        def send(self, data: str) -> None:
            msg = _json.loads(data)
            if self._round == 1 and msg["type"] == "hello":
                raise ConnectionClosedError(Close(4404, "unknown worker"),
                                            Close(4404, "unknown worker"))
            if msg["type"] == "hello":
                stop.set()  # second hello accepted: end the test

        def recv(self, timeout: float | None = None):
            raise TimeoutError()

        def close(self) -> None:
            pass

    def fake_connect(url: str, **kwargs):
        attempts.append(url)
        return FakeWS(len(attempts))

    monkeypatch.setattr(_sync_client, "connect", fake_connect)
    ws_client.ws_loop(
        coordinator_url="http://127.0.0.1:8000", worker_id="wid",
        stop_event=stop, ws_connected=connected, wake_event=wake,
        heartbeat_interval=30.0, timeout=1.0,
        policy_file=tmp_path / "policy.json",
    )
    assert len(attempts) == 2  # rejected hello reconnected instead of dying
    assert attempts[0].startswith("ws://127.0.0.1:8000/ws/worker/wid")
    assert not connected.is_set()


def test_no_ws_flag_defaults_off():
    assert parse_args(["--loop"]).no_ws is False
    assert parse_args(["--loop", "--no-ws"]).no_ws is True


def test_wait_returns_immediately_on_wake():
    stop, wake = threading.Event(), threading.Event()
    wake.set()
    started = time.monotonic()
    _wait_for_next_tick(stop, wake, 30.0)
    assert time.monotonic() - started < 5.0
    assert not wake.is_set()  # wake is consumed


def test_wait_sleeps_full_interval_when_quiet():
    stop, wake = threading.Event(), threading.Event()
    started = time.monotonic()
    _wait_for_next_tick(stop, wake, 0.05)
    assert time.monotonic() - started >= 0.05


def test_wait_breaks_early_on_stop():
    stop, wake = threading.Event(), threading.Event()
    stop.set()
    started = time.monotonic()
    _wait_for_next_tick(stop, wake, 30.0)
    assert time.monotonic() - started < 5.0


def test_ws_connected_skips_http_heartbeat(monkeypatch, tmp_path):
    """While the socket is up the socket owns heartbeats — never both channels."""
    events: list[str] = []
    started_ws: list[dict] = []
    monkeypatch.setattr(
        main_mod, "register_worker",
        lambda *a, **k: events.append("register") or {"id": "ok"},
    )
    monkeypatch.setattr(main_mod, "_attempt_report_capabilities", lambda *a, **k: None)
    monkeypatch.setattr(main_mod, "send_heartbeat",
                        lambda *a, **k: events.append("heartbeat") or {"status": "ok"})
    monkeypatch.setattr(main_mod, "report_resources",
                        lambda *a, **k: events.append("resources"))
    monkeypatch.setattr(main_mod, "_availability",
                        lambda policy: ((True, "ok"),
                                        {"available": True, "paused": False, "reason": "ok"},
                                        {"cpu_percent": 1.0}))
    monkeypatch.setattr(main_mod, "claim_work", lambda *a, **k: None)  # idle queue

    class OneShotEvent:
        def __init__(self) -> None:
            self._waits = 0

        def is_set(self) -> bool:
            return self._waits >= 3

        def set(self) -> None:
            self._waits = 99

        def wait(self, _seconds: float) -> bool:
            self._waits += 1
            return False

    ws_connected = threading.Event()
    ws_connected.set()  # socket already up: HTTP heartbeat must be skipped
    args = parse_args(["--loop", "--interval", "0.01", "--heartbeat-interval", "0.02",
                       "--worker-id-file", str(tmp_path / "wid")])
    assert main_mod.run_worker(args, OneShotEvent(),  # type: ignore[arg-type]
                               ws_connected=ws_connected,
                               ws_loop_fn=lambda **k: started_ws.append(k) or None) == 0
    assert "heartbeat" not in events  # socket owned it
    assert events.count("resources") == 2  # telemetry still flows every tick
    assert started_ws and started_ws[0]["worker_id"]
