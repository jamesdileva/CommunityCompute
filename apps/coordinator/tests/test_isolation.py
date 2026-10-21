"""Sprint 30: tenant isolation — Customer A cannot reach Customer B's job or data."""

from fastapi.testclient import TestClient

from packages.protocol.workloads import definition_for, verify_definition

WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"


def _mint(client: TestClient, name: str) -> str:
    resp = client.post("/api/v1/customers", json={"name": name})
    assert resp.status_code == 201, resp.text
    key = resp.json()["api_key"]
    funded = client.post(
        "/api/v1/billing/topup", headers=_auth(key), json={"amount_cents": 1000}
    )
    assert funded.status_code == 201, funded.text
    return key


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def _submit(client: TestClient, key: str, total: int = 1, chunk: int = 1) -> str:
    resp = client.post(
        "/api/v1/jobs", headers=_auth(key),
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": total, "chunk_size": chunk},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _register_worker(client: TestClient, wid: str = WORKER_A) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "PC-A"},
    ).status_code == 200


def _complete_all(client: TestClient, wid: str = WORKER_A) -> None:
    while True:
        unit = client.post(f"/work/{wid}/claim", json={}).json()
        if not unit:
            return
        assert client.post(
            f"/work/{unit['work_unit_id']}/result",
            json={"worker_id": wid, "status": "completed",
                  "value": unit["range_end"], "metrics": {"execution_ms": 1.0}},
        ).status_code == 200


# ---- identity -----------------------------------------------------------------


def test_me_returns_authenticated_identity(client: TestClient):
    created = client.post("/api/v1/customers", json={"name": "Acme"}).json()
    me = client.get("/api/v1/me", headers=_auth(created["api_key"])).json()
    assert me == {"customer_id": created["id"], "name": "Acme", "status": "active"}


def test_suspended_customer_key_stops_working(client: TestClient):
    created = client.post("/api/v1/customers", json={"name": "Acme"}).json()
    key = created["api_key"]
    assert client.get("/api/v1/me", headers=_auth(key)).status_code == 200
    # suspend directly through the DB the API uses
    from app.db import get_db
    from app.main import app
    from app.models.customer import Customer
    from sqlalchemy.orm import Session

    db: Session = next(iter(app.dependency_overrides[get_db]()))
    try:
        db.get(Customer, created["id"]).status = "suspended"
        db.commit()
    finally:
        db.close()
    assert client.get("/api/v1/me", headers=_auth(key)).status_code == 401


# ---- signed workload definitions ----------------------------------------------


def test_workloads_are_served_signed(client: TestClient):
    key = _mint(client, "Acme")
    manifests = client.get("/api/v1/workloads", headers=_auth(key)).json()
    names = {m["name"] for m in manifests}
    assert names == {"hello_compute", "stats_range", "embeddings", "image_generate"}
    for manifest in manifests:
        sig = manifest.pop("signature")
        local = definition_for(manifest["name"]).to_manifest()
        assert manifest == local  # served contract matches the local catalog
        assert verify_definition(
            local, sig, "dev-insecure-signing-key-do-not-use-in-production"
        )


def test_job_records_pinned_workload_version(client: TestClient):
    key = _mint(client, "Acme")
    job_id = _submit(client, key)
    from app.db import get_db
    from app.main import app
    from app.models.job import Job

    db = next(iter(app.dependency_overrides[get_db]()))
    try:
        job = db.get(Job, job_id)
        assert job.workload_version == "1"
        assert job.isolation_scope.startswith("customer:")
    finally:
        db.close()


# ---- authorization matrix -----------------------------------------------------


def test_customer_a_cannot_read_customer_b_job_or_results(client: TestClient):
    a = _mint(client, "A")
    b = _mint(client, "B")
    job = _submit(client, a, total=2, chunk=1)
    assert client.get(f"/api/v1/jobs/{job}", headers=_auth(b)).status_code == 404
    assert client.get(f"/api/v1/jobs/{job}/results", headers=_auth(b)).status_code == 404
    # A still sees its own job
    assert client.get(f"/api/v1/jobs/{job}", headers=_auth(a)).status_code == 200


def test_job_listing_is_scoped_to_owner(client: TestClient):
    a = _mint(client, "A")
    b = _mint(client, "B")
    ja = _submit(client, a)
    jb = _submit(client, b)
    a_ids = {j["id"] for j in client.get("/api/v1/jobs", headers=_auth(a)).json()}
    b_ids = {j["id"] for j in client.get("/api/v1/jobs", headers=_auth(b)).json()}
    assert a_ids == {ja} and b_ids == {jb}


def test_results_data_never_leaks_across_tenants(client: TestClient):
    a = _mint(client, "A")
    b = _mint(client, "B")
    _register_worker(client)
    job = _submit(client, a, total=2, chunk=1)
    _complete_all(client)
    a_results = client.get(f"/api/v1/jobs/{job}/results", headers=_auth(a)).json()
    assert all(r["ok"] for r in a_results["results"])
    # B gets nothing back at all for the same job id
    assert client.get(f"/api/v1/jobs/{job}/results", headers=_auth(b)).status_code == 404


def test_operator_job_scope_is_not_customer(client: TestClient):
    """A dashboard/operator job carries scope 'operator', invisible to customers."""
    key = _mint(client, "A")
    operator_job = client.post(
        "/jobs", json={"workload_type": "hello_compute", "params": {"op": "sum"},
                       "total_units": 1, "chunk_size": 1},
    ).json()["id"]
    assert client.get(f"/api/v1/jobs/{operator_job}", headers=_auth(key)).status_code == 404
