"""Sprint 6/7: work claim/submit client + worker work cycle behavior."""

import httpx
import pytest

import worker.main as main_mod
from worker.work import claim_work, submit_result


def test_claim_work_returns_none_when_empty(monkeypatch):
    def fake_post(url, timeout=None):
        assert url.endswith("/claim")
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    assert claim_work("http://127.0.0.1:8000", "w1") is None


def test_claim_work_returns_assignment(monkeypatch):
    assignment = {"protocol_version": "0.1.0-sprint6", "work_unit_id": "u1",
                  "job_id": "j1", "workload_type": "hello_compute",
                  "range_start": 1, "range_end": 10, "params": {"op": "sum"},
                  "lease_id": "l1", "attempt_number": 1}

    def fake_post(url, timeout=None):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json=assignment, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    got = claim_work("http://127.0.0.1:8000", "w1")
    assert got["work_unit_id"] == "u1"


def test_submit_result_ok(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"ok": True, "work_unit_id": "u1"}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    body = submit_result("http://127.0.0.1:8000", "u1", {"status": "completed", "value": 55})
    assert body["ok"] is True


def test_submit_result_rejection_raises(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        request = httpx.Request("POST", url)
        return httpx.Response(422, json={"error": "verification failed"}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(httpx.HTTPStatusError):
        submit_result("http://127.0.0.1:8000", "u1", {"status": "completed", "value": -1})


def test_submit_result_409_is_handled(monkeypatch):
    """Sprint 7: a late result for an already-completed unit returns, never raises."""

    def fake_post(url, json=None, timeout=None):
        request = httpx.Request("POST", url)
        return httpx.Response(409, json={"error": "already completed by another worker"},
                              request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    got = submit_result("http://127.0.0.1:8000", "u1",
                        {"status": "completed", "value": 55})
    assert got == {"status": "already_completed"}


def test_work_cycle_executes_and_submits(monkeypatch):
    """Loop tick: claim → execute (known answer) → submit verified payload."""
    submitted: list[dict] = []

    monkeypatch.setattr(
        main_mod, "claim_work",
        lambda *a, **k: {"protocol_version": "0.1.0-sprint6", "work_unit_id": "u9",
                         "job_id": "j9", "workload_type": "hello_compute",
                         "range_start": 1, "range_end": 10, "params": {"op": "sum"}},
    )

    def fake_submit(url, unit_id, body, timeout=None):
        submitted.append(body)
        return {"ok": True}

    monkeypatch.setattr(main_mod, "submit_result", fake_submit)
    main_mod._attempt_work_cycle("http://127.0.0.1:8000", "w1", 5.0)
    assert len(submitted) == 1
    assert submitted[0]["value"] == 55
    assert submitted[0]["status"] == "completed"
    assert submitted[0]["output_hash"]
