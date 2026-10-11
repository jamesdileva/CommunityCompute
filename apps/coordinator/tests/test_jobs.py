"""Sprint 5: job submission, work-unit generation, status endpoint."""

import uuid

from fastapi.testclient import TestClient


def _submit(client: TestClient, **overrides) -> dict:
    body = {
        "workload_type": "hello_compute",
        "params": {"op": "sum"},
        "total_units": 1000,
        "chunk_size": 100,
        **overrides,
    }
    resp = client.post("/jobs", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_submit_creates_exactly_ten_units(client: TestClient):
    job = _submit(client)
    assert job["status"] == "queued"
    detail = client.get(f"/jobs/{job['id']}").json()
    units = detail["work_units"]
    assert len(units) == 10
    assert detail["counts"] == {"queued": 10}
    assert [u["sequence"] for u in units] == list(range(1, 11))
    assert units[0]["range_start"] == 1 and units[0]["range_end"] == 100
    assert units[-1]["range_start"] == 901 and units[-1]["range_end"] == 1000
    ids = {u["id"] for u in units}
    assert len(ids) == 10  # unique identifiers
    assert all(u["job_id"] == job["id"] for u in units)


def test_job_params_immutable_after_creation(client: TestClient):
    params = {"op": "hash", "algo": "sha256"}
    job = _submit(client, params=params)
    detail = client.get(f"/jobs/{job['id']}").json()
    assert detail["params"] == params
    # params dict mutation in test must not have leaked into the job row
    params["op"] = "mutated"
    detail2 = client.get(f"/jobs/{job['id']}").json()
    assert detail2["params"]["op"] == "hash"


def test_reject_non_positive_totals(client: TestClient):
    for bad in (0, -5):
        resp = client.post(
            "/jobs",
            json={"workload_type": "hello_compute", "total_units": bad, "chunk_size": 10},
        )
        assert resp.status_code == 422
    resp = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "total_units": 100, "chunk_size": 0},
    )
    assert resp.status_code == 422


def test_reject_missing_workload_type(client: TestClient):
    resp = client.post("/jobs", json={"total_units": 10, "chunk_size": 5})
    assert resp.status_code == 422


def test_unknown_job_404(client: TestClient):
    resp = client.get(f"/jobs/{str(uuid.uuid4())}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == 404


def test_job_list(client: TestClient):
    a = _submit(client)
    b = _submit(client, total_units=10, chunk_size=5)
    ids = {j["id"] for j in client.get("/jobs").json()}
    assert {a["id"], b["id"]} <= ids
