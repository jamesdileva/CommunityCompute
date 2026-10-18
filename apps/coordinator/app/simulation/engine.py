"""Large-scale scheduling simulation (Sprint 32).

Measures scheduler + capacity behavior from 100 up to 1,000,000 simulated
nodes without materializing the fleet or touching the database:

- **streaming aggregate** (O(1) memory): capacity totals, hardware-class mix,
  online fraction, and an expected-throughput estimate across every node;
- **sampled scheduling** (bounded work): the *real* ``compat.check`` and
  ``scoring.score`` run on a deterministic sample of worker↔unit pairs, so the
  match rate and score distribution reflect the production decision path, not
  a re-implementation.

The whole point is that cost is O(scale) with a small constant and a fixed
sample, so a million nodes is a few seconds and a flat few MB.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Iterator
from dataclasses import dataclass

from app.services import scoring
from app.services.compat import check
from app.simulation.workers import SimulatedWorker, make_workers

# Representative unit templates: a mix of open CPU work, model-cached work,
# and GPU-gated work. Requirements match the real schema keys, and the types
# are the real workload names (Sprint 33 adds the GPU-gated image_generate).
_UNITS: tuple[dict, ...] = (
    {"workload_type": "hello_compute", "requirements": {}},
    {"workload_type": "stats_range", "requirements": {"cpu_cores": 4}},
    {"workload_type": "embeddings", "requirements": {"model": "llama3-8b"}},
    {"workload_type": "image_generate",
     "requirements": {"gpu": True, "min_vram_mb": 8192}},
)

DEFAULT_SAMPLE = 2000
DEFAULT_CHUNK = 10_000


@dataclass(slots=True)
class ScaleReport:
    scale: int
    online_workers: int
    total_cores: int
    total_vram_gb: float
    total_ram_gb: float
    total_bandwidth_gbps: float
    expected_units_per_min: float
    class_mix: dict
    sample_size: int
    compatible: int
    incompatible: int
    match_rate: float
    score_mean: float
    score_p50: float
    score_p90: float
    cache_hit_rate: float
    elapsed_ms: float

    def as_row(self) -> dict:
        return {
            "scale": f"{self.scale:,}",
            "online": f"{self.online_workers:,}",
            "cores": f"{self.total_cores:,}",
            "vram_gb": round(self.total_vram_gb, 1),
            "ram_gb": round(self.total_ram_gb, 1),
            "bw_gbps": round(self.total_bandwidth_gbps, 2),
            "units/min": f"{self.expected_units_per_min:,.0f}",
            "match%": round(self.match_rate * 100, 1),
            "score_p50": round(self.score_p50, 3),
            "cache%": round(self.cache_hit_rate * 100, 1),
            "ms": round(self.elapsed_ms, 1),
        }


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[idx]


def simulate_scale(
    scale: int,
    *,
    seed: int = 32,
    sample_size: int = DEFAULT_SAMPLE,
    chunk: int = DEFAULT_CHUNK,
    units: tuple[dict, ...] = _UNITS,
    settings=None,
) -> ScaleReport:
    """Run one scale point. Streams workers in chunks; keeps a bounded sample."""
    if scale <= 0:
        raise ValueError("scale must be positive")
    settings = settings or scoring.get_settings()
    stride = max(1, scale // max(1, sample_size))

    online = 0
    cores = 0
    vram_mb = 0
    ram_mb = 0
    bandwidth_mbps = 0.0
    expected_rate = 0.0
    class_mix: dict[str, int] = {}

    scores: list[float] = []
    compatible = 0
    model_pairs = 0
    model_hits = 0
    sampled = 0

    started = time.perf_counter()
    buffered: list[SimulatedWorker] = []
    for index, worker in enumerate(make_workers(scale, seed=seed)):
        buffered.append(worker)
        # aggregate
        if worker.is_online():
            online += 1
        cores += worker.cores
        vram_mb += worker.vram_mb
        ram_mb += worker.ram_mb
        bandwidth_mbps += worker.bandwidth_mbps
        expected_rate += worker.units_per_min * worker.availability
        class_mix[worker.klass] = class_mix.get(worker.klass, 0) + 1

        # bounded, deterministic scheduling sample using the REAL decision path
        if index % stride == 0 and sampled < sample_size:
            unit = units[sampled % len(units)]
            reqs = unit["requirements"]
            profile = worker.profile()
            ok, _reason = check(reqs, profile)
            if ok:
                compatible += 1
                result = scoring.score_with_context(
                    worker.score_context(), requirements=reqs,
                    range_start=1, range_end=1, settings=settings,
                )
                scores.append(result["total"])
            if reqs.get("model"):
                model_pairs += 1
                if reqs["model"] in worker.cached:
                    model_hits += 1
            sampled += 1

        if len(buffered) >= chunk:
            buffered.clear()

    buffered.clear()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return ScaleReport(
        scale=scale,
        online_workers=online,
        total_cores=cores,
        total_vram_gb=vram_mb / 1024,
        total_ram_gb=ram_mb / 1024,
        total_bandwidth_gbps=bandwidth_mbps / 1000,
        expected_units_per_min=expected_rate,
        class_mix=class_mix,
        sample_size=sampled,
        compatible=compatible,
        incompatible=sampled - compatible,
        match_rate=(compatible / sampled if sampled else 0.0),
        score_mean=(round(statistics.fmean(scores), 6) if scores else 0.0),
        score_p50=round(_percentile(scores, 0.5), 6),
        score_p90=round(_percentile(scores, 0.9), 6),
        cache_hit_rate=(model_hits / model_pairs if model_pairs else 0.0),
        elapsed_ms=elapsed_ms,
    )


def run_scales(
    scales: Iterator[int] | list[int], *, seed: int = 32, **kwargs
) -> list[ScaleReport]:
    return [simulate_scale(scale, seed=seed, **kwargs) for scale in scales]
