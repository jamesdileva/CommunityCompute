"""Sprint 37: paid compute — prepaid balances, rate card, compensation split.

Exit condition: *a controlled customer can pay for a supported workload and
the system can calculate contributor/network compensation.* No real money
moves; the only provider is simulated.
"""

import importlib.util
from pathlib import Path

import pytest
from app.services.billing import (
    DEFAULT_RATE_CARD,
    split_unit_price,
)
from app.services.payments import SimulatedProvider, get_provider
from fastapi.testclient import TestClient
from settings_override import override_settings

REPO_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "paid_compute_demo", REPO_ROOT / "scripts" / "paid_compute_demo.py"
)
assert _spec and _spec.loader
paid_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(paid_demo)

WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"
WORKER_B = "bbbbbbbb-0000-0000-0000-000000000002"


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def _mint(client: TestClient, name: str = "Acme") -> dict:
    resp = client.post("/api/v1/customers", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _topup(client: TestClient, key: str, cents: int = 1000) -> dict:
    resp = client.post("/api/v1/billing/topup", headers=_auth(key),
                       json={"amount_cents": cents})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _register(client: TestClient, wid: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "PC-A"},
    ).status_code == 200


def _submit(client: TestClient, key: str, total: int = 1, chunk: int = 1,
            verify_sample: float = 0.0) -> dict:
    resp = client.post(
        "/api/v1/jobs", headers=_auth(key),
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": total, "chunk_size": chunk,
              "verify_sample": verify_sample},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _claim(client: TestClient, wid: str) -> dict:
    unit = client.post(f"/work/{wid}/claim", json={}).json()
    assert unit, "expected queued work"
    return unit


def _complete(client: TestClient, wid: str, value=None) -> dict:
    unit = _claim(client, wid)
    value = unit["range_end"] if value is None else value
    resp = client.post(
        f"/work/{unit['work_unit_id']}/result",
        json={"worker_id": wid, "status": "completed", "value": value,
              "metrics": {"execution_ms": 1.0}},
    )
    assert resp.status_code == 200, resp.text
    return unit


def _earnings(client: TestClient, wid: str) -> dict:
    resp = client.get(f"/workers/{wid}/earnings")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _network(client: TestClient) -> dict:
    resp = client.get("/billing/network")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---- pricing -----------------------------------------------------------------


def test_default_rate_card_and_split():
    assert DEFAULT_RATE_CARD["hello_compute"] == 5
    assert split_unit_price(5, 20) == (4, 1)   # 20% of 5 = 1 cent
    assert split_unit_price(5, 0) == (5, 0)
    assert split_unit_price(5, 100) == (0, 5)
    contributor, network = split_unit_price(3, 20)
    assert contributor + network == 3


def test_rate_card_override_merges(client: TestClient):
    with override_settings(
        PRICING_RATE_CARD='{"hello_compute": 7}', PRICING_NETWORK_FEE_PERCENT="50"
    ):
        pricing = client.get("/billing/pricing").json()
        assert pricing["rate_card"]["hello_compute"] == 7
        assert pricing["rate_card"]["stats_range"] == DEFAULT_RATE_CARD["stats_range"]
        assert pricing["network_fee_percent"] == 50
        assert split_unit_price(7, 50) == (3, 4)


def test_bad_rate_card_fails_closed():
    from app.services import billing

    with override_settings(PRICING_RATE_CARD="not-json"), pytest.raises(ValueError):
        billing.rate_card()


def test_catalog_includes_price(client: TestClient):
    catalog = client.get("/workloads").json()
    by_name = {w["name"]: w for w in catalog}
    assert by_name["hello_compute"]["price_cents_per_unit"] == 5
    assert by_name["hello_compute"]["currency"] == "USD"


# ---- prepaid balance ---------------------------------------------------------


def test_topup_credits_balance(client: TestClient):
    customer = _mint(client)
    result = _topup(client, customer["api_key"], 500)
    assert result["status"] == "succeeded"
    assert result["provider"] == "simulated"
    assert result["provider_ref"].startswith("sim_")
    assert result["balance_cents"] == 500

    summary = client.get("/api/v1/billing", headers=_auth(customer["api_key"])).json()
    assert summary["balance_cents"] == 500
    assert summary["lifetime_topup_cents"] == 500
    assert summary["lifetime_charged_cents"] == 0
    assert summary["rate_card"]["hello_compute"] == 5


def test_topup_bounds(client: TestClient):
    key = _mint(client)["api_key"]
    too_small = client.post("/api/v1/billing/topup", headers=_auth(key),
                            json={"amount_cents": 99})
    assert too_small.status_code == 422
    too_large = client.post("/api/v1/billing/topup", headers=_auth(key),
                            json={"amount_cents": 100_001})
    assert too_large.status_code == 422
    zero = client.post("/api/v1/billing/topup", headers=_auth(key),
                       json={"amount_cents": 0})
    assert zero.status_code == 422


def test_topup_requires_customer_key(client: TestClient):
    assert client.post("/api/v1/billing/topup",
                       json={"amount_cents": 500}).status_code == 401


def test_submit_debits_prepaid_balance(client: TestClient):
    key = _mint(client)["api_key"]
    _topup(client, key, 100)
    job = _submit(client, key, total=2, chunk=1)
    summary = client.get("/api/v1/billing", headers=_auth(key)).json()
    assert summary["balance_cents"] == 90  # 2 units x 5 cents
    assert summary["lifetime_charged_cents"] == 10
    assert summary["charges"][0]["job_id"] == job["id"]
    assert summary["charges"][0]["unit_price_cents"] == 5


def test_submit_shortfall_402_leaves_no_job(client: TestClient):
    key = _mint(client)["api_key"]
    resp = client.post(
        "/api/v1/jobs", headers=_auth(key),
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": 2, "chunk_size": 1},
    )
    assert resp.status_code == 402
    detail = resp.json()["error"]["message"]
    assert detail["need_cents"] == 10 and detail["balance_cents"] == 0
    assert client.get("/api/v1/jobs", headers=_auth(key)).json() == []
    assert client.get("/api/v1/billing", headers=_auth(key)).json()["balance_cents"] == 0


def test_operator_job_stays_free(client: TestClient):
    _register(client, WORKER_A)
    resp = client.post("/jobs", json={"workload_type": "hello_compute",
                                      "params": {"op": "sum"},
                                      "total_units": 1, "chunk_size": 1})
    assert resp.status_code == 201
    _complete(client, WORKER_A)
    assert _network(client)["charged_cents"] == 0
    assert _earnings(client, WORKER_A)["balance_cents"] == 0


# ---- compensation ------------------------------------------------------------


def test_verified_units_split_between_contributor_and_network(client: TestClient):
    key = _mint(client)["api_key"]
    _topup(client, key, 100)
    _register(client, WORKER_A)
    _submit(client, key, total=2, chunk=1)
    for _ in range(2):
        _complete(client, WORKER_A)

    earnings = _earnings(client, WORKER_A)
    assert earnings["balance_cents"] == 8  # 2 x (5 - 1) cents
    assert all(e["amount_cents"] == 4 for e in earnings["entries"])

    net = _network(client)
    assert net["charged_cents"] == 10
    assert net["contributor_cents"] == 8
    assert net["network_cents"] == 2
    assert net["unallocated_cents"] == 0
    assert net["by_workload"] == {"hello_compute": 10}


def test_duplicate_verification_is_not_paid(client: TestClient):
    key = _mint(client)["api_key"]
    _topup(client, key, 100)
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    _submit(client, key, total=1, chunk=1, verify_sample=1.0)
    _complete(client, WORKER_A)
    _complete(client, WORKER_B)  # duplicate reproduces the same value

    assert _earnings(client, WORKER_A)["balance_cents"] == 4
    assert _earnings(client, WORKER_B)["balance_cents"] == 0
    net = _network(client)
    assert net["contributor_cents"] == 4 and net["network_cents"] == 1


def test_overturn_voids_contributor_but_keeps_network_fee(client: TestClient):
    key = _mint(client)["api_key"]
    _topup(client, key, 100)
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    _submit(client, key, total=1, chunk=1, verify_sample=1.0)
    _complete(client, WORKER_A)
    duplicate = _claim(client, WORKER_B)
    resp = client.post(
        f"/work/{duplicate['work_unit_id']}/result",
        json={"worker_id": WORKER_B, "status": "completed", "value": -1,
              "metrics": {"execution_ms": 1.0}},
    )
    assert resp.status_code == 422  # disagreement -> overturn

    earnings = _earnings(client, WORKER_A)
    assert earnings["balance_cents"] == 0
    assert earnings["entries"][0]["voided"] is True
    net = _network(client)
    assert net["contributor_cents"] == 0
    assert net["network_cents"] == 1  # fee retained for the failed attempt


def test_failed_unit_has_no_compensation(client: TestClient):
    key = _mint(client)["api_key"]
    _topup(client, key, 100)
    _register(client, WORKER_A)
    _submit(client, key, total=1, chunk=1)
    unit = _claim(client, WORKER_A)
    resp = client.post(
        f"/work/{unit['work_unit_id']}/result",
        json={"worker_id": WORKER_A, "status": "completed", "value": -1},
    )
    assert resp.status_code == 422
    assert _earnings(client, WORKER_A)["balance_cents"] == 0


# ---- operator + isolation ----------------------------------------------------


def test_operator_billing_views(client: TestClient):
    customer = _mint(client, "Acme")
    _topup(client, customer["api_key"], 250)
    accounts = client.get("/billing/accounts").json()
    assert [a["customer_id"] for a in accounts] == [customer["id"]]
    assert accounts[0]["balance_cents"] == 250

    pricing = client.get("/billing/pricing").json()
    assert pricing["currency"] == "USD"
    assert pricing["network_fee_percent"] == 20

    net = client.get("/billing/network").json()
    assert net["topup_cents"] == 250
    assert net["jobs"] == 0


def test_balances_are_per_customer(client: TestClient):
    a = _mint(client, "A")
    b = _mint(client, "B")
    _topup(client, a["api_key"], 300)
    _topup(client, b["api_key"], 700)
    assert client.get("/api/v1/billing", headers=_auth(a["api_key"])).json()["balance_cents"] == 300
    assert client.get("/api/v1/billing", headers=_auth(b["api_key"])).json()["balance_cents"] == 700


def test_worker_earnings_unknown_worker_404(client: TestClient):
    assert client.get("/workers/nope/earnings").status_code == 404


# ---- provider seam -----------------------------------------------------------


def test_simulated_provider_moves_no_money():
    provider = SimulatedProvider()
    result = provider.charge(customer_id="c", amount_cents=500,
                             currency="USD", reference="topup:c")
    assert result.ok and result.provider == "simulated"
    assert result.provider_ref.startswith("sim_")
    assert provider.charge(customer_id="c", amount_cents=0, currency="USD",
                           reference="x").ok is False
    assert get_provider("simulated") is get_provider("simulated")
    with pytest.raises(ValueError):
        get_provider("stripe")


# ---- exit-proof verdict + docs ----------------------------------------------


def test_demo_verdict_accepts_a_balanced_split():
    job = {"status": "completed"}
    billing = {"lifetime_charged_cents": 20, "balance_cents": 80}
    earnings = {"balance_cents": 16}
    network = {"network_cents": 4}
    verdict = paid_demo.summarize(job, billing, earnings, network, 100)
    assert verdict["ok"] is True
    assert verdict["split_ok"] is True
    assert verdict["funded_ok"] is True


def test_demo_verdict_rejects_a_missing_fee_or_incomplete_job():
    job = {"status": "completed"}
    billing = {"lifetime_charged_cents": 20, "balance_cents": 80}
    earnings = {"balance_cents": 20}
    network = {"network_cents": 0}
    assert paid_demo.summarize(job, billing, earnings, network, 100)["ok"] is False
    assert paid_demo.summarize(
        {"status": "running"}, billing, earnings, {"network_cents": 0}, 100
    )["ok"] is False


def test_demo_render_states_the_exit_condition():
    verdict = paid_demo.summarize(
        {"status": "completed"},
        {"lifetime_charged_cents": 20, "balance_cents": 80},
        {"balance_cents": 16}, {"network_cents": 4}, 100,
    )
    text = paid_demo.render(verdict, 100)
    assert "exit condition met   : yes" in text
    assert "simulated money" in text


def test_pricing_doc_covers_money_and_non_goals():
    doc = (REPO_ROOT / "docs" / "pricing.md").read_text(encoding="utf-8")
    for needle in ("No real money moves", "simulated", "rate card",
                   "network fee", "402", "non-goal"):
        assert needle.lower() in doc.lower(), needle
