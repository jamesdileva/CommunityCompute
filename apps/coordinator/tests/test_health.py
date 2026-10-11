"""Sprint 1: /health proves alive + SQLite connected; error envelope; worker count."""

from fastapi.testclient import TestClient

from app.api.health import SERVICE, VERSION
from app.db import get_db
from app.main import app
from app.models.worker import Worker


def test_health_ok_with_database(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == SERVICE
    assert body["version"] == VERSION
    assert body["database"] == {"connected": True, "workers": 0}


def test_health_counts_workers(client: TestClient):
    db = next(iter(app.dependency_overrides[get_db]()))
    db.add(Worker(id="11111111-1111-1111-1111-111111111111", worker_version="0.1.0"))
    db.commit()
    db.close()
    assert client.get("/health").json()["database"]["workers"] == 1


def test_unknown_route_returns_error_envelope(client: TestClient):
    resp = client.get("/no-such-route")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == 404
