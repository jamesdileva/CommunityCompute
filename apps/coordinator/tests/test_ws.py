"""Sprint 17: WebSocket control plane — hello, heartbeat reuse, fan-out wiring."""

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.services.ws_registry import ConnectionRegistry, registry


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.clear()
    yield
    registry.clear()


def _register(client: TestClient, wid: str | None = None) -> str:
    wid = wid or str(uuid.uuid4())
    resp = client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "0.1.0-sprint17", "hostname": "PC-A"},
    )
    assert resp.status_code == 200
    return wid


def test_ws_hello_ack(client: TestClient):
    wid = _register(client)
    with client.websocket_connect(f"/ws/worker/{wid}") as ws:
        assert registry.is_connected(wid)
        ws.send_json({"type": "hello"})
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"
        assert ack["server_time"]
    assert not registry.is_connected(wid)


def test_ws_heartbeat_reuses_http_logic(client: TestClient):
    wid = _register(client)
    with client.websocket_connect(f"/ws/worker/{wid}") as ws:
        ws.send_json(
            {
                "type": "heartbeat",
                "resources": {"cpu_percent": 12.5, "ram_available_mb": 8000,
                              "gpu_percent": None},
                "availability": {"available": True, "paused": False, "reason": "ws test"},
            }
        )
        ack = ws.receive_json()
        assert ack["type"] == "heartbeat_ack"
        assert ack["status"] == "online"
    worker = client.get(f"/workers/{wid}").json()
    assert worker["status"] == "online"
    assert worker["cpu_percent"] == 12.5
    log = client.get(f"/workers/{wid}/heartbeats").json()
    assert len(log) == 1


def test_ws_heartbeat_bad_shape_reports_error(client: TestClient):
    wid = _register(client)
    with client.websocket_connect(f"/ws/worker/{wid}") as ws:
        ws.send_json({"type": "heartbeat", "resources": {"cpu_percent": 9999}})
        reply = ws.receive_json()
        assert reply["type"] == "error"


def test_ws_unknown_message_type_reports_error(client: TestClient):
    wid = _register(client)
    with client.websocket_connect(f"/ws/worker/{wid}") as ws:
        ws.send_json({"type": "bogus"})
        reply = ws.receive_json()
        assert reply["type"] == "error"


def test_ws_unknown_worker_refused(client: TestClient):
    wid = str(uuid.uuid4())
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/worker/{wid}") as ws:
            ws.receive_json()


def test_pause_sends_frame(client: TestClient, monkeypatch):
    wid = _register(client)
    sent: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        registry, "send_from_thread",
        lambda worker_id, message: sent.append((worker_id, message)) or True,
    )
    assert client.post(f"/workers/{wid}/pause").status_code == 200
    assert sent == [(wid, {"type": "pause"})]
    assert client.post(f"/workers/{wid}/resume").status_code == 200
    assert sent[-1] == (wid, {"type": "resume"})


def test_job_submit_broadcasts_work_available(client: TestClient, monkeypatch):
    _register(client)
    sent: list[dict] = []
    monkeypatch.setattr(
        registry, "broadcast_from_thread", lambda message: sent.append(message) or 0
    )
    resp = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": 2, "chunk_size": 1},
    )
    assert resp.status_code == 201
    assert len(sent) == 1
    assert sent[0]["type"] == "work_available"
    assert sent[0]["job_id"] == resp.json()["id"]


def test_registry_send_and_broadcast():
    reg = ConnectionRegistry()

    class FakeSocket:
        def __init__(self) -> None:
            self.sent: list[dict] = []

        async def send_json(self, message: dict) -> None:
            self.sent.append(message)

    async def _run() -> None:
        import asyncio as _asyncio

        loop = _asyncio.get_running_loop()
        a, b = FakeSocket(), FakeSocket()
        reg.register("a", a, loop)  # type: ignore[arg-type]
        reg.register("b", b, loop)  # type: ignore[arg-type]
        assert reg.is_connected("a")
        assert sorted(reg.connected_workers()) == ["a", "b"]
        assert await reg.send("a", {"type": "ping"}) is True
        assert a.sent == [{"type": "ping"}]
        reg.unregister("a", a)  # type: ignore[arg-type]
        assert not reg.is_connected("a")
        assert await reg.send("a", {"type": "ping"}) is False

    asyncio.run(_run())
