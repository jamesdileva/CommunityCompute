"""Sprint 0: worker ping test with mocked transport (no live server needed)."""

import httpx

from worker.main import ping_coordinator


def test_ping_coordinator_ok(monkeypatch):
    def fake_get(url, timeout=None, headers=None, verify=True):
        assert url.endswith("/health")
        assert headers and "X-Worker-Id" in headers
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"status": "ok", "service": "coordinator"}, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    body = ping_coordinator("http://127.0.0.1:8000", "00000000-0000-0000-0000-000000000000")
    assert body["status"] == "ok"
