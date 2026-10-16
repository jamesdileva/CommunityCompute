"""Sprint 29: the customer API — a separate client submits work without the dashboard."""

from fastapi.testclient import TestClient

WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"


def _mint(client: TestClient, name: str = "Acme") -> dict:
    resp = client.post("/api/v1/customers", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def _register_worker(client: TestClient, wid: str = WORKER_A) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "PC-A"},
    ).status_code == 200


def _submit(client: TestClient, key: str, total: int = 1, chunk: int = 1) -> dict:
    resp = client.post(
        "/api/v1/jobs",
        headers=_auth(key),
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": total, "chunk_size": chunk},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _complete_all(client: TestClient, wid: str = WORKER_A) -> None:
    while True:
        unit = client.post(f"/work/{wid}/claim", json={}).json()
        if not unit:
            return
        resp = client.post(
            f"/work/{unit['work_unit_id']}/result",
            json={"worker_id": wid, "status": "completed",
                  "value": unit["range_end"], "metrics": {"execution_ms": 1.0}},
        )
        assert resp.status_code == 200, resp.text


# ---- operator: customers + keys ----------------------------------------------


def test_create_customer_returns_key_once(client: TestClient):
    created = _mint(client, "Acme")
    assert created["name"] == "Acme" and created["api_key"].startswith("cc_")
    listed = client.get("/api/v1/customers").json()
    assert [c["id"] for c in listed] == [created["id"]]
    assert listed[0]["active_keys"] == 1
    keys = client.get(f"/api/v1/customers/{created['id']}/keys").json()
    assert len(keys) == 1 and keys[0]["prefix"] == created["api_key"][:11]
    assert "api_key" not in keys[0] and "key_hash" not in keys[0]


def test_rotate_key_invalidates_old(client: TestClient):
    created = _mint(client)
    old = created["api_key"]
    rotated = client.post(f"/api/v1/customers/{created['id']}/rotate-key").json()
    new = rotated["api_key"]
    assert new != old
    assert client.get("/api/v1/usage", headers=_auth(old)).status_code == 401
    assert client.get("/api/v1/usage", headers=_auth(new)).status_code == 200


def test_revoke_customer_keys(client: TestClient):
    created = _mint(client)
    key = created["api_key"]
    resp = client.post(f"/api/v1/customers/{created['id']}/revoke")
    assert resp.status_code == 200 and resp.json()["revoked"] == 1
    assert client.get("/api/v1/usage", headers=_auth(key)).status_code == 401


# ---- authentication -----------------------------------------------------------


def test_jobs_require_a_customer_key(client: TestClient):
    assert client.post("/api/v1/jobs", json={}).status_code == 401
    assert client.post("/api/v1/jobs", headers=_auth("nope"), json={}).status_code == 401


def test_worker_token_is_not_a_customer_key(client: TestClient):
    """Separate trust domains: a worker bearer never authorizes the customer API."""
    _register_worker(client)
    enroll = client.post("/auth/enrollment-tokens", json={}).json()["token"]
    worker_token = client.post("/auth/enroll", json={"enrollment_token": enroll}).json()["token"]
    assert client.get("/api/v1/usage", headers=_auth(worker_token)).status_code == 401


# ---- submit / status / results ------------------------------------------------


def test_submit_and_poll_status(client: TestClient):
    key = _mint(client)["api_key"]
    job = _submit(client, key, total=3, chunk=1)
    assert job["status"] == "queued" and job["total_units"] == 3
    status = client.get(f"/api/v1/jobs/{job['id']}", headers=_auth(key)).json()
    assert status["counts"] == {"queued": 3}


def test_result_retrieval_and_aggregate(client: TestClient):
    key = _mint(client)["api_key"]
    _register_worker(client)
    job = _submit(client, key, total=3, chunk=1)
    _complete_all(client)
    results = client.get(f"/api/v1/jobs/{job['id']}/results", headers=_auth(key)).json()
    assert results["status"] == "completed"
    assert results["aggregate"]["final"] == 1 + 2 + 3  # sum of per-unit range_end
    assert [r["value"] for r in results["results"]] == [1, 2, 3]
    assert all(r["ok"] for r in results["results"])


def test_customer_cannot_see_anothers_job(client: TestClient):
    a = _mint(client, "A")["api_key"]
    b = _mint(client, "B")["api_key"]
    job = _submit(client, a, total=1, chunk=1)
    assert client.get(f"/api/v1/jobs/{job['id']}", headers=_auth(b)).status_code == 404
    assert client.get(f"/api/v1/jobs/{job['id']}/results", headers=_auth(b)).status_code == 404
    # and the unknown-job path is the same 404 (no existence leak)
    assert client.get("/api/v1/jobs/does-not-exist", headers=_auth(a)).status_code == 404


def test_unknown_workload_rejected(client: TestClient):
    key = _mint(client)["api_key"]
    resp = client.post(
        "/api/v1/jobs",
        headers=_auth(key),
        json={"workload_type": "rm -rf", "params": {}, "total_units": 1, "chunk_size": 1},
    )
    assert resp.status_code == 422


# ---- usage accounting ---------------------------------------------------------


def test_usage_accounting(client: TestClient):
    key = _mint(client)["api_key"]
    _register_worker(client)
    _submit(client, key, total=2, chunk=1)
    _submit(client, key, total=3, chunk=1)
    _complete_all(client)
    usage = client.get("/api/v1/usage", headers=_auth(key)).json()
    assert usage["jobs"] == 2 and usage["units"] == 5
    assert usage["units_by_status"] == {"completed": 5}
    assert usage["units_by_workload"] == {"hello_compute": 5}


def test_customer_jobs_are_not_charged_credits(client: TestClient):
    """Free community pool: customer jobs never write a spend row."""
    key = _mint(client)["api_key"]
    _register_worker(client)
    _submit(client, key, total=2, chunk=1)
    _complete_all(client)
    ledger = client.get("/credits/ledger").json()
    assert all(r["reason"] != "spend_job_submit" for r in ledger)
    # the completing worker still earns for verified work
    assert client.get(f"/workers/{WORKER_A}/credits").json()["balance"] == 2
