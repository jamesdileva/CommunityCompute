"""Sprint 15: scheduler preference for cache-warm workers (ordering, not a gate)."""

import uuid

from fastapi.testclient import TestClient

WORKER_CACHED = "aaaaaaaa-0000-0000-0000-000000000001"
WORKER_PLAIN = "bbbbbbbb-0000-0000-0000-000000000002"
MODEL = "hashing-embedder@1"


def _register(client: TestClient, wid: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "PC-A"},
    ).status_code == 200


def _submit(client: TestClient, requirements: dict, total: int = 1) -> str:
    resp = client.post(
        "/jobs",
        json={"workload_type": "embeddings", "params": {"dim": 16},
              "total_units": total, "chunk_size": total, "requirements": requirements},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _claim(client: TestClient, wid: str, cached: list[str] | None = None) -> dict:
    body = {} if cached is None else {"cached_models": cached}
    return client.post(f"/work/{wid}/claim", json=body).json()


def test_cached_worker_gets_model_unit_first(client: TestClient):
    _register(client, WORKER_CACHED)
    _submit(client, {})  # plain unit queued FIRST ...
    _submit(client, {"model": MODEL})  # ... model unit queued SECOND
    got = _claim(client, WORKER_CACHED, [MODEL])
    detail = client.get(f"/jobs/{got['job_id']}").json()
    assert detail["requirements"] == {"model": MODEL}  # skipped ahead to the model unit


def test_uncached_worker_still_served_plain_unit(client: TestClient):
    """Preference must never starve: uncached workers get non-model work."""
    _register(client, WORKER_PLAIN)
    _submit(client, {})
    _submit(client, {"model": MODEL})
    got = _claim(client, WORKER_PLAIN, [])
    detail = client.get(f"/jobs/{got['job_id']}").json()
    assert detail["requirements"] == {}  # plain unit, not the model one


def test_claim_without_cache_list_stays_fifo(client: TestClient):
    _register(client, WORKER_PLAIN)
    first = _submit(client, {})
    second = _submit(client, {"model": MODEL})
    got = _claim(client, WORKER_PLAIN)  # old-style claim, no body list
    jobs = client.get(f"/jobs/{got['job_id']}").json()
    assert got["job_id"] == first  # strict FIFO preserved
