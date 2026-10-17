"""Sprint 31: scheduling score (components, weighting, FIFO tie-break, benchmark).

The benchmark is the exit-condition artifact: it replays a synthetic unit/worker
pool and shows the scored scheduler moves *fewer model bytes* than FIFO.
"""

import pytest
from app.services import scoring
from fastapi.testclient import TestClient
from settings_override import override_settings

WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"
WORKER_B = "bbbbbbbb-0000-0000-0000-000000000002"


def _profile(cached: tuple[str, ...] = (), cpu: int = 8, ram_mb: int = 16384) -> dict:
    return {
        "cpu": {"logical_cores": cpu, "physical_cores": cpu},
        "ram": {"total_mb": ram_mb},
        "os": {"system": "Windows"},
        "gpus": [],
        "cached_models": [{"name": n, "version": "1"} for n in cached],
    }


def _ctx(cached=(), mean_ms=50.0, rel=0.5, cpu=8, ram_mb=16384) -> dict:
    return {
        "profile": _profile(tuple(cached), cpu=cpu, ram_mb=ram_mb),
        "reliability": rel,
        "mean_execution_ms": mean_ms,
        "cpu_percent": 0,
        "gpu_percent": 0,
        "active_leases": 0,
        "max_leases": 1,
        "reported_cached_models": set(cached),
    }


# --- component tests (pure) ---------------------------------------------------


def test_capability_fit_rewards_headroom_on_needed_axis():
    # a GPU job is judged on GPU headroom alone
    big = _profile() | {"gpus": [{"vendor": "nvidia", "vram_mb": 24576}]}
    small = _profile() | {"gpus": [{"vendor": "nvidia", "vram_mb": 4096}]}
    reqs = {"gpu": True, "gpu_vendor": "nvidia", "min_vram_mb": 4096}
    assert scoring.capability_fit(reqs, big) > scoring.capability_fit(reqs, small)


def test_capability_fit_averages_when_unconstrained():
    weak = _profile(cpu=2, ram_mb=4096)
    strong = _profile(cpu=16, ram_mb=65536)
    assert scoring.capability_fit({}, strong) > scoring.capability_fit({}, weak)


def test_estimated_speed_neutral_then_faster_is_higher():
    assert scoring.estimated_speed(None) == 0.5
    fast = scoring.estimated_speed(5.0)
    slow = scoring.estimated_speed(500.0)
    assert 0.0 < slow < 0.5 < fast < 1.0


def test_cached_model_component():
    assert scoring.cached_model({"model": "m1"}, {"m1"}) == 1.0
    assert scoring.cached_model({"model": "m1"}, set()) == 0.0
    assert scoring.cached_model({}, {"m1"}) == 0.0


def test_reliability_neutral_when_unrated():
    assert scoring.reliability(None) == 0.5
    assert scoring.reliability(0.9) == 0.9


def test_availability_prefers_idle_worker_with_headroom():
    idle = scoring.availability(5.0, 0.0, active_leases=0, max_leases=4)
    loaded = scoring.availability(95.0, 0.0, active_leases=0, max_leases=4)
    hoarding = scoring.availability(5.0, 0.0, active_leases=4, max_leases=4)
    assert idle > loaded
    assert idle > hoarding
    assert scoring.availability(None, None, 0, 4) == 0.5


def test_transfer_cost_uncached_model_dominates_cached():
    reqs = {"model": "m1", "model_mb": 500}
    cached = scoring.transfer_cost(1, 1, reqs, {"m1"})
    uncached = scoring.transfer_cost(1, 1, reqs, set())
    assert cached == 0.0
    assert uncached == 1.0  # 500MB > 50MB reference → saturated


def test_location_penalty_only_on_explicit_mismatch():
    assert scoring.location_penalty({}, _profile()) == 0.0
    assert scoring.location_penalty({"location": "eu"}, _profile()) == 0.0
    assert scoring.location_penalty({"location": "eu"}, {"location": "eu"}) == 0.0
    assert scoring.location_penalty({"location": "eu"}, {"location": "us"}) == 1.0


def test_score_cached_model_beats_uncached_for_same_worker():
    reqs = {"model": "m1", "model_mb": 500}
    cached = scoring.score(requirements=reqs, range_start=1, range_end=1,
                           profile=_profile(("m1",)), cached_models={"m1"})
    uncached = scoring.score(requirements=reqs, range_start=1, range_end=1,
                             profile=_profile(), cached_models=set())
    assert cached["total"] > uncached["total"]
    assert cached["components"]["cached_model"] == 1.0


def test_rank_ties_break_to_fifo():
    from datetime import datetime, timezone

    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 3, tzinfo=timezone.utc)
    entries = [
        (1.0, t2, 2, "second"),
        (1.0, t1, 1, "first"),
        (2.0, t3, 3, "best"),
    ]
    ordered = [e[3] for e in scoring.rank(entries)]
    assert ordered == ["best", "first", "second"]


# --- benchmark: scored vs FIFO (exit condition) -------------------------------


def _simulate(units: list[dict], workers: list[tuple[str, ...]], *, scored: bool):
    """Discrete-round greedy sim. Returns (transfers_by_worker, makespan_rounds).

    Equal-speed workers start idle; each round every idle worker takes one
    unit (FIFO: the oldest; scored: the best-scoring for *that* worker). A
    model download is charged once per worker per model, then cached.
    """
    pending = list(units)
    cached = [set(w) for w in workers]
    transfers = 0
    rounds = 0
    while pending:
        rounds += 1
        for i in range(len(workers)):
            if not pending:
                break
            if scored:
                ctx = _ctx(cached[i])
                best = max(
                    range(len(pending)),
                    key=lambda k: (
                        scoring.score_with_context(
                            ctx, requirements=pending[k]["requirements"],
                            range_start=pending[k]["start"], range_end=pending[k]["end"],
                        )["total"],
                        -k,  # FIFO tie-break: prefer the older (lower) index
                    ),
                )
            else:
                best = 0
            chosen = pending.pop(best)
            model = chosen["requirements"].get("model")
            if model and model not in cached[i]:
                transfers += chosen["requirements"].get("model_mb", 256) * 1024 * 1024
                cached[i].add(model)
    return transfers, rounds


def _benchmark_units() -> list[dict]:
    model = {"model": "m1", "model_mb": 500}
    return [
        {"requirements": {}, "start": 1, "end": 1},
        {"requirements": model, "start": 1, "end": 1},
        {"requirements": model, "start": 1, "end": 1},
        {"requirements": model, "start": 1, "end": 1},
        {"requirements": {}, "start": 1, "end": 1},
        {"requirements": {}, "start": 1, "end": 1},
    ]


def test_benchmark_scored_scheduler_reduces_transfer_vs_fifo():
    units = _benchmark_units()
    workers = [("m1",), (), (), ()]  # one worker already holds the model
    fifo_transfers, fifo_rounds = _simulate(units, workers, scored=False)
    scored_transfers, scored_rounds = _simulate(units, workers, scored=True)
    # FIFO hands model units to three cold workers (3 downloads); scoring
    # routes them to the cached worker (1 download) without slowing down.
    assert fifo_transfers == 3 * 500 * 1024 * 1024
    assert scored_transfers == 1 * 500 * 1024 * 1024
    assert scored_transfers < fifo_transfers
    assert scored_rounds <= fifo_rounds  # throughput not regressed


# --- integration: claim ordering + explain ------------------------------------


def _register(client: TestClient, worker_id: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": worker_id, "worker_version": "0.1.0-sprint31", "hostname": "PC"},
    ).status_code == 200


def _report_caps(client: TestClient, worker_id: str, cached: tuple[str, ...] = ()) -> None:
    assert client.post(f"/workers/{worker_id}/capabilities", json=_profile(cached)).status_code == 200


def _submit(client: TestClient, requirements: dict | None = None) -> str:
    resp = client.post(
        "/jobs",
        json={
            "workload_type": "hello_compute",
            "params": {"op": "sum"},
            "total_units": 1,
            "chunk_size": 1,
            "requirements": requirements or {},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_claim_prefers_unit_whose_model_is_cached(client: TestClient):
    _register(client, WORKER_A)
    _report_caps(client, WORKER_A, cached=("m1",))
    plain = _submit(client)  # older (FIFO first)
    cached_job = _submit(client, {"model": "m1"})
    claimed = client.post(f"/work/{WORKER_A}/claim").json()
    assert claimed["job_id"] == cached_job  # scoring beats FIFO here
    assert plain  # (kept for intent; plain unit still exists)


def test_scoring_disabled_falls_back_to_fifo(client: TestClient):
    _register(client, WORKER_A)
    _report_caps(client, WORKER_A, cached=("m1",))
    oldest = _submit(client)
    _submit(client, {"model": "m1"})
    with override_settings(SCORING_ENABLED="false"):
        claimed = client.post(f"/work/{WORKER_A}/claim").json()
    assert claimed["job_id"] == oldest


def test_explain_includes_score_breakdown(client: TestClient):
    _register(client, WORKER_A)
    _report_caps(client, WORKER_A, cached=("m1",))
    job_id = _submit(client, {"model": "m1"})
    payload = client.get(f"/jobs/{job_id}/compatibility/{WORKER_A}").json()
    assert payload["compatible"] is True
    score = payload["score"]
    assert score["components"]["cached_model"] == 1.0
    assert set(score["contributions"]) == set(score["components"])
    assert score["total"] == pytest.approx(
        sum(score["contributions"][k] for k in scoring.POSITIVE)
        - sum(score["contributions"][k] for k in scoring.NEGATIVE),
        abs=1e-6,
    )


def test_incompatible_worker_never_scores_or_claims(client: TestClient):
    _register(client, WORKER_B)  # weak box
    _report_caps(client, WORKER_B)
    job_id = _submit(client, {"cpu_cores": 999})
    # explain reports incompatible and omits a score
    payload = client.get(f"/jobs/{job_id}/compatibility/{WORKER_B}").json()
    assert payload["compatible"] is False and "score" not in payload
    # and the weak worker can't claim the incompatible unit
    assert client.post(f"/work/{WORKER_B}/claim").json() == {}
