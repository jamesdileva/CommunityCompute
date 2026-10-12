"""Sprint 3: profile assembly + capability report client payload."""

import httpx

from worker.capabilities.discover import discover_capabilities
from worker.capabilities.schema import SCHEMA_VERSION


def test_profile_is_complete_and_versioned():
    profile = discover_capabilities()
    assert profile.schema_version == SCHEMA_VERSION
    assert profile.cpu.arch
    assert profile.ram.total_mb and profile.ram.total_mb > 0
    assert profile.os.system
    assert len(profile.gpus) >= 1  # UnknownProvider guarantees a slot
    payload = profile.model_dump()
    assert set(payload) == {"schema_version", "cpu", "ram", "os", "gpus", "runtimes",
                            "cached_models"}
    assert "hello_compute" in payload["runtimes"]


def test_report_capabilities_ok(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        assert url.endswith("/capabilities")
        request = httpx.Request("POST", url)
        return httpx.Response(200, json=json, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    from worker.capabilities.client import report_capabilities

    profile = discover_capabilities()
    body = report_capabilities("http://127.0.0.1:8000", "worker-x", profile)
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["gpus"]


def test_report_capabilities_failure_raises(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", fake_post)
    from worker.capabilities.client import report_capabilities

    profile = discover_capabilities()
    try:
        report_capabilities("http://127.0.0.1:8000", "worker-x", profile)
    except httpx.ConnectError:
        return
    raise AssertionError("expected ConnectError to propagate to caller")
