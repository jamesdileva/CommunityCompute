"""Sprint 10: explain() breakdown + the scheduler-explanation endpoint."""

import uuid

from fastapi.testclient import TestClient

from app.services.explain import explain

PROFILE = {
    "cpu": {"logical_cores": 12, "physical_cores": 6},
    "ram": {"total_mb": 16258},
    "os": {"system": "Windows", "release": "11"},
    "gpus": [{"vendor": "amd", "model": "RX 6400", "vram_mb": 4080}],
    "runtimes": ["hello_compute"],
}


def test_no_requirements_matches_everything():
    out = explain({}, PROFILE)
    assert out == {"compatible": True, "reason": "no requirements", "checks": []}


def test_no_profile_rejected():
    out = explain({"cpu_cores": 1}, None)
    assert out["compatible"] is False
    assert out["reason"] == "no capabilities reported"


def test_breakdown_rows_for_each_dimension():
    out = explain({"cpu_cores": 4, "ram_mb": 1024, "gpu": True,
                   "gpu_vendor": "amd", "os": "Windows"}, PROFILE)
    assert out["compatible"] is True
    dims = [c["dimension"] for c in out["checks"]]
    assert dims == ["cpu_cores", "ram_mb", "os", "gpu"]
    assert all(c["passed"] for c in out["checks"])
    assert all(c["reason"] == "ok" for c in out["checks"])


def test_failed_rows_carry_reason_and_overall_false():
    out = explain({"gpu": True, "gpu_vendor": "nvidia", "min_vram_mb": 24000}, PROFILE)
    assert out["compatible"] is False
    row = out["checks"][0]
    assert row["dimension"] == "gpu" and row["passed"] is False
    assert "nvidia" in row["reason"]


def test_runtime_row():
    ok = explain({"runtime": "hello_compute"}, PROFILE)
    assert ok["compatible"] and ok["checks"][0]["need"] == "hello_compute"
    bad = explain({"runtime": "cuda"}, PROFILE)
    assert bad["compatible"] is False
    assert bad["checks"][0]["have"] == ["hello_compute"]


def test_endpoint_explains_job_vs_worker(client: TestClient):
    wid = str(uuid.uuid4())
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "t"},
    ).status_code == 200
    assert client.post(f"/workers/{wid}/capabilities", json=PROFILE).status_code == 200
    job = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "total_units": 1, "chunk_size": 1,
              "requirements": {"gpu": True, "gpu_vendor": "nvidia"}},
    ).json()
    resp = client.get(f"/jobs/{job['id']}/compatibility/{wid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["compatible"] is False
    assert body["checks"][0]["dimension"] == "gpu"


def test_worker_detail_includes_tiers(client: TestClient):
    wid = str(uuid.uuid4())
    client.post("/workers/register",
                json={"worker_id": wid, "worker_version": "t", "hostname": "t"})
    assert client.get(f"/workers/{wid}").json()["tiers"] is None
    client.post(f"/workers/{wid}/capabilities", json=PROFILE)
    tiers = client.get(f"/workers/{wid}").json()["tiers"]
    assert tiers == {"gpu": "H1", "cpu": "H2", "ram": "H2"}


def test_endpoint_404s(client: TestClient):
    wid = str(uuid.uuid4())
    assert client.get(f"/jobs/{uuid.uuid4()}/compatibility/{wid}").status_code == 404
    client.post("/workers/register",
                json={"worker_id": wid, "worker_version": "t", "hostname": "t"})
    assert client.get(
        f"/jobs/{uuid.uuid4()}/compatibility/{wid}"
    ).status_code == 404  # unknown job
