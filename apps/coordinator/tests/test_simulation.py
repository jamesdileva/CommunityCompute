"""Sprint 32: large-scale simulation (streaming fleet + sampled scheduler + DB)."""

import pytest
from app.db import Base
from app.services import scoring
from app.simulation import make_workers, run_db_backed, run_scales, simulate_scale
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/sim.db",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


# --- synthetic fleet ----------------------------------------------------------


def test_make_workers_is_deterministic():
    a = [(w.id, w.klass, w.vram_mb, w.cores, w.availability, w.cached)
         for w in make_workers(200, seed=7)]
    b = [(w.id, w.klass, w.vram_mb, w.cores, w.availability, w.cached)
         for w in make_workers(200, seed=7)]
    assert a == b
    c = [(w.id, w.klass, w.vram_mb) for w in make_workers(200, seed=8)]
    assert c != a


def test_worker_attributes_are_sane():
    for worker in make_workers(500, seed=3):
        assert worker.cores > 0 and worker.ram_mb > 0
        assert worker.vram_mb >= 0
        assert 0.0 <= worker.availability <= 1.0
        assert 0.0 <= worker.reliability <= 1.0
        assert worker.location in {"na", "eu", "apac", "sa"}
        assert worker.bandwidth_mbps > 0


def test_worker_shapes_feed_the_real_scheduler():
    worker = next(make_workers(1, seed=1))
    profile = worker.profile()
    assert {"cpu", "ram", "os", "gpus", "cached_models"} <= set(profile)
    result = scoring.score_with_context(
        worker.score_context(), requirements={}, range_start=1, range_end=1)
    assert set(result["components"])  # scoring accepted the synthetic profile


# --- streaming scale engine ---------------------------------------------------


def test_simulate_scale_reports_are_sane():
    report = simulate_scale(10_000, sample_size=500)
    assert report.scale == 10_000
    assert 0 <= report.online_workers <= 10_000
    assert report.total_cores > 0
    assert report.sample_size <= 500  # bounded work regardless of scale
    assert 0.0 <= report.match_rate <= 1.0
    assert 0.0 < report.expected_units_per_min
    assert report.elapsed_ms >= 0


def test_simulate_scale_is_deterministic():
    a = simulate_scale(5_000, sample_size=400, seed=11)
    b = simulate_scale(5_000, sample_size=400, seed=11)
    assert (a.online_workers, a.total_cores, a.total_vram_gb, a.match_rate,
            a.score_p50, a.cache_hit_rate) == (
        b.online_workers, b.total_cores, b.total_vram_gb, b.match_rate,
        b.score_p50, b.cache_hit_rate)


def test_capacity_grows_with_scale():
    small = simulate_scale(1_000)
    big = simulate_scale(100_000)
    assert big.total_cores > small.total_cores
    assert big.online_workers > small.online_workers
    assert big.expected_units_per_min > small.expected_units_per_min


def test_real_scheduler_filters_and_scores_in_the_sample():
    # the catalog mixes open + cpu + model + gpu units against a mixed fleet,
    # so the *real* compat filter must both accept and reject pairs.
    report = simulate_scale(20_000, sample_size=1000)
    assert report.compatible > 0
    assert report.incompatible > 0
    assert 0.0 < report.match_rate < 1.0


def test_run_scales_returns_one_report_each():
    reports = run_scales([100, 1_000])
    assert [r.scale for r in reports] == [100, 1_000]


def test_million_node_point_is_cheap():
    # the headline scale must stream, not materialize: bounded sample + flat time
    report = simulate_scale(1_000_000, sample_size=1000)
    assert report.scale == 1_000_000
    assert report.sample_size <= 1000
    assert report.online_workers > 0


# --- real database / queue validation -----------------------------------------


def test_db_backed_registers_workers_and_drains_queue(db):
    stats = run_db_backed(db, workers=60, units=60, seed=5)
    assert stats["workers_used"] > 0
    assert stats["completed"] == 60
    assert stats["job_status"] == "completed"
    assert stats["aggregate_final"] == stats["expected_final"] == 60 * 61 // 2
    assert stats["rows_per_second"] > 0


def test_db_backed_handles_more_units_than_workers(db):
    stats = run_db_backed(db, workers=20, units=45, seed=6)
    assert stats["completed"] == 45
    assert stats["aggregate_final"] == stats["expected_final"] == 45 * 46 // 2
    # 20 workers must have looped for more than one unit each
    assert stats["claimed"] > stats["workers_used"]
