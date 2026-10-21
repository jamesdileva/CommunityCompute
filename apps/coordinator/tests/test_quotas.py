"""Sprint 30: per-customer resource quotas enforced at submit."""

from fastapi.testclient import TestClient
from settings_override import override_settings


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


def _submit(client: TestClient, key: str, total: int = 1, chunk: int = 1):
    return client.post(
        "/api/v1/jobs", headers=_auth(key),
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": total, "chunk_size": chunk},
    )


def test_units_per_job_cap(client: TestClient):
    key = _mint(client, "A")
    with override_settings(CUSTOMER_MAX_UNITS_PER_JOB="5"):
        resp = _submit(client, key, total=6)
        assert resp.status_code == 413
        detail = resp.json()["error"]["message"]
        assert detail["scope"] == "units_per_job" and detail["limit"] == 5


def test_in_flight_jobs_cap(client: TestClient):
    key = _mint(client, "A")
    with override_settings(CUSTOMER_MAX_IN_FLIGHT_JOBS="1"):
        assert _submit(client, key).status_code == 201
        resp = _submit(client, key)
        assert resp.status_code == 429
        assert resp.json()["error"]["message"]["scope"] == "in_flight_jobs"


def test_units_in_flight_cap(client: TestClient):
    key = _mint(client, "A")
    with override_settings(CUSTOMER_MAX_IN_FLIGHT_JOBS="10",
                           CUSTOMER_MAX_UNITS_IN_FLIGHT="3"):
        assert _submit(client, key, total=2).status_code == 201
        resp = _submit(client, key, total=2)  # 2 + 2 > 3
        assert resp.status_code == 429
        assert resp.json()["error"]["message"]["scope"] == "units_in_flight"


def test_quota_is_per_customer(client: TestClient):
    a = _mint(client, "A")
    b = _mint(client, "B")
    with override_settings(CUSTOMER_MAX_IN_FLIGHT_JOBS="1"):
        assert _submit(client, a).status_code == 201
        # B's quota is independent of A's in-flight job
        assert _submit(client, b).status_code == 201


def test_quota_endpoint_reports_limits_and_usage(client: TestClient):
    key = _mint(client, "A")
    with override_settings(CUSTOMER_MAX_UNITS_PER_JOB="7",
                           CUSTOMER_MAX_IN_FLIGHT_JOBS="3",
                           CUSTOMER_MAX_UNITS_IN_FLIGHT="42"):
        quota = client.get("/api/v1/quota", headers=_auth(key)).json()
        assert quota["max_units_per_job"] == 7
        assert quota["max_in_flight_jobs"] == 3
        assert quota["max_units_in_flight"] == 42
        assert quota == {
            "max_units_per_job": 7, "max_in_flight_jobs": 3, "max_units_in_flight": 42,
            "in_flight_jobs": 0, "units_in_flight": 0,
        }
        assert _submit(client, key, total=2, chunk=1).status_code == 201
        quota = client.get("/api/v1/quota", headers=_auth(key)).json()
        assert quota["in_flight_jobs"] == 1 and quota["units_in_flight"] == 2
