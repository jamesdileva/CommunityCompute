"""Sprint 0: coordinator liveness test (Sprint 1 adds SQLite connectivity assertion)."""

from fastapi.testclient import TestClient

from app.main import VERSION, app


def test_health_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "coordinator"
    assert body["version"] == VERSION
