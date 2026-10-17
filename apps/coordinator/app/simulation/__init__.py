"""Large-scale simulation harness (Sprint 32).

Public surface:
- ``simulate_scale`` / ``run_scales`` — streaming, sampled scheduler simulation
  (safe to 1,000,000 nodes; see ``engine``);
- ``make_workers`` / ``SimulatedWorker`` — the synthetic fleet (``workers``);
- ``run_db_backed`` — small real-database validation (``db_backed``).
"""

from app.simulation.db_backed import register_simulated_workers, run_db_backed
from app.simulation.engine import DEFAULT_SAMPLE, ScaleReport, run_scales, simulate_scale
from app.simulation.workers import SimulatedWorker, make_workers

__all__ = [
    "DEFAULT_SAMPLE",
    "ScaleReport",
    "SimulatedWorker",
    "make_workers",
    "register_simulated_workers",
    "run_db_backed",
    "run_scales",
    "simulate_scale",
]
