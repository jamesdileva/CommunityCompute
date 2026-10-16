"""Sprint 28: earn by contributing, spend by consuming — no free money."""

import uuid

from fastapi.testclient import TestClient

from app.services.credits import (
    InsufficientCredits,
    balance,
    earn_verified_unit,
    spend_job_submit,
)

WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"
WORKER_B = "bbbbbbbb-0000-0000-0000-000000000002"


def _register(client: TestClient, wid: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "PC-A"},
    ).status_code == 200


def _submit(client: TestClient, total: int = 1, chunk: int = 1,
            submitter: str | None = None) -> str:
    body = {"workload_type": "hello_compute", "params": {"op": "sum"},
            "total_units": total, "chunk_size": chunk}
    if submitter:
        body["submitter_worker_id"] = submitter
    resp = client.post("/jobs", json=body)
    assert resp.status_code == 201
    return resp.json()["id"]


def _claim_complete(client: TestClient, wid: str, value=None) -> dict:
    unit = client.post(f"/work/{wid}/claim", json={}).json()
    assert unit, "expected queued work"
    unit_id = unit["work_unit_id"]
    value = unit["range_end"] if value is None else value
    resp = client.post(
        f"/work/{unit_id}/result",
        json={"worker_id": wid, "status": "completed", "value": value,
              "metrics": {"execution_ms": 1.0}},
    )
    assert resp.status_code == 200, resp.text
    return unit


# ---- issuance ----------------------------------------------------------------


def test_completing_units_earns_credits(client: TestClient):
    _register(client, WORKER_A)
    _submit(client, total=3, chunk=1)
    for _ in range(3):
        _claim_complete(client, WORKER_A)
    assert client.get(f"/workers/{WORKER_A}/credits").json() == {
        "worker_id": WORKER_A, "balance": 3, "earned": 3, "spent": 0,
    }


def test_failed_unit_earns_nothing(client: TestClient):
    _register(client, WORKER_A)
    _submit(client, total=1, chunk=1)
    unit = client.post(f"/work/{WORKER_A}/claim", json={}).json()
    assert client.post(
        f"/work/{unit['work_unit_id']}/result",
        json={"worker_id": WORKER_A, "status": "completed", "value": -1},
    ).status_code == 422
    assert client.get(f"/workers/{WORKER_A}/credits").json()["balance"] == 0


def test_self_dealing_earns_nothing(client: TestClient):
    """Submitting your own job still costs; the wage-side earns back 0."""
    _register(client, WORKER_A)
    _submit(client, total=3, chunk=1)
    for _ in range(3):
        _claim_complete(client, WORKER_A)  # +3 earned
    _submit(client, total=3, chunk=1, submitter=WORKER_A)  # -3 spent
    _claim_complete(client, WORKER_A)  # own unit: no credit
    row = client.get(f"/workers/{WORKER_A}/credits").json()
    assert row == {"worker_id": WORKER_A, "balance": 0, "earned": 3, "spent": 3}


# ---- spending ----------------------------------------------------------------


def test_submit_with_submitter_deducts(client: TestClient):
    _register(client, WORKER_A)
    _submit(client, total=3, chunk=1)
    for _ in range(3):
        _claim_complete(client, WORKER_A)  # balance 3
    _submit(client, total=2, chunk=1, submitter=WORKER_A)  # spend 2
    totals_a = client.get(f"/workers/{WORKER_A}/credits").json()
    assert totals_a == {"worker_id": WORKER_A, "balance": 1, "earned": 3, "spent": 2}


def test_submitter_shortfall_402(client: TestClient):
    _register(client, WORKER_A)
    resp = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": 2, "chunk_size": 1, "submitter_worker_id": WORKER_A},
    )
    assert resp.status_code == 402
    body = resp.json()["error"]["message"]
    assert body["need"] == 2 and body["have"] == 0
    assert client.get("/jobs").json() == []  # no orphaned job on shortfall


def test_submitter_unknown_worker_404(client: TestClient):
    wid = str(uuid.uuid4())
    resp = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": 1, "chunk_size": 1, "submitter_worker_id": wid},
    )
    assert resp.status_code == 404


def test_anonymous_submit_is_free(client: TestClient):
    _register(client, WORKER_A)
    _submit(client, submitter=None)  # no deduction, backwards compatible
    assert client.get(f"/workers/{WORKER_A}/credits").json()["balance"] == 0


# ---- ledger -------------------------------------------------------------------


def test_ledger_after_earning_then_spending(client: TestClient):
    _register(client, WORKER_A)
    _submit(client, total=2, chunk=1)  # free open-pool work
    for _ in range(2):  # earn 2
        _claim_complete(client, WORKER_A)
    _submit(client, submitter=WORKER_A)  # spend 1
    rows = client.get("/credits/ledger").json()
    assert len(rows) == 3
    assert rows[0]["amount"] == -1 and rows[0]["reason"] == "spend_job_submit"
    assert sorted(r["amount"] for r in rows[1:]) == [1, 1]


def test_balance_matches_ledger_sum(client: TestClient):
    from app.db import get_db
    from app.main import app

    _register(client, WORKER_A)
    _submit(client, total=2, chunk=1)
    for _ in range(2):
        _claim_complete(client, WORKER_A)
    db = next(iter(app.dependency_overrides[get_db]()))
    try:
        assert balance(db, WORKER_A) == 2
    finally:
        db.close()


# ---- service-level invariants -------------------------------------------------


def test_spend_refuses_partial_deduction():
    class _Query:
        def filter_by(self, **_kw):
            return self

        def scalar(self):
            return 0  # balance zero

    class _DB:
        def query(self, *_a, **_kw):
            return _Query()

        def add(self, _row):
            raise AssertionError("must not write")

    try:
        spend_job_submit(_DB(), worker_id="w", job_id="j", units=3)
    except InsufficientCredits:
        return
    raise AssertionError("expected InsufficientCredits")


def test_earn_returns_false_on_self_deal():
    class _DB:
        def add(self, _row):
            raise AssertionError("must not write")

        def commit(self):
            raise AssertionError("must not commit")

    assert earn_verified_unit(_DB(), worker_id="w", job_id="j", work_unit_id="u",
                              submitter_worker_id="w") is False
