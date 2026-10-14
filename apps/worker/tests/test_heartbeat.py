"""Sprint 4: heartbeat payload + send client."""

import httpx

from worker.heartbeat import build_heartbeat_payload, send_heartbeat


def test_payload_shape_and_values():
    payload = build_heartbeat_payload("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert payload["worker_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    r = payload["resources"]
    assert set(r) == {"cpu_percent", "ram_available_mb", "gpu_percent"}
    assert r["cpu_percent"] is None or 0 <= r["cpu_percent"] <= 100
    assert r["ram_available_mb"] is None or r["ram_available_mb"] > 0


def test_send_heartbeat_ok(monkeypatch):
    def fake_post(url, json=None, timeout=None, verify=True, **kw):
        assert "/heartbeat" in url
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"status": "online", "server_time": "now"},
                              request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    body = send_heartbeat("http://127.0.0.1:8000",
                          build_heartbeat_payload("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    assert body["status"] == "online"


def test_send_heartbeat_failure_raises(monkeypatch):
    def fake_post(url, json=None, timeout=None, verify=True, **kw):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", fake_post)
    try:
        send_heartbeat("http://127.0.0.1:8000",
                       build_heartbeat_payload("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    except httpx.ConnectError:
        return
    raise AssertionError("expected ConnectError to propagate")
