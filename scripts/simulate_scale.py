"""Large-scale scheduler simulation driver (Sprint 32).

Streams 100 → 1,000 → 10,000 → 100,000 simulated nodes by default (add
``--include-1m`` for the million-node point) and prints capacity + scheduling
metrics. Optionally runs a small real-database validation.

Safe on a laptop: the fleet is streamed (O(1) memory) and the real scheduler
runs on a bounded sample. No node is persisted or spawned.

Usage:
    python scripts/simulate_scale.py
    python scripts/simulate_scale.py --include-1m --sample 4000
    python scripts/simulate_scale.py --scales 100,1000 --db-workers 200
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "coordinator"))


def _print_table(reports) -> None:
    columns = list(reports[0].as_row().keys())
    widths = {c: max(len(c), *(len(str(r.as_row()[c])) for r in reports)) for c in columns}
    header = "  ".join(c.rjust(widths[c]) for c in columns)
    print("\n" + header)
    print("  ".join("-" * widths[c] for c in columns))
    for report in reports:
        row = report.as_row()
        print("  ".join(str(row[c]).rjust(widths[c]) for c in columns))


def main() -> int:
    parser = argparse.ArgumentParser(description="CommunityCompute scale simulation (Sprint 32)")
    parser.add_argument("--scales", default="100,1000,10000,100000",
                        help="comma-separated node counts")
    parser.add_argument("--include-1m", action="store_true",
                        help="also run the 1,000,000-node point (heaviest)")
    parser.add_argument("--sample", type=int, default=2000,
                        help="sampled worker<->unit scheduling decisions per scale")
    parser.add_argument("--seed", type=int, default=32)
    parser.add_argument("--db-workers", type=int, default=0,
                        help="if >0, run a real-DB validation with this many workers")
    args = parser.parse_args()

    scales = [int(s) for s in args.scales.split(",") if s.strip()]
    if args.include_1m and 1_000_000 not in scales:
        scales.append(1_000_000)

    from app.simulation import simulate_scale

    reports = []
    for scale in scales:
        report = simulate_scale(scale, seed=args.seed, sample_size=args.sample)
        reports.append(report)
        print(f"  scale {scale:>9,}  {report.elapsed_ms:8.1f} ms  "
              f"match {report.match_rate * 100:5.1f}%  "
              f"score p50 {report.score_p50:6.3f}  cache {report.cache_hit_rate * 100:5.1f}%")

    _print_table(reports)
    mix = reports[-1].class_mix
    print("\nclass mix @", f"{reports[-1].scale:,}", ":", dict(sorted(mix.items())))

    if args.db_workers > 0:
        from app.db import Base
        from app.simulation import run_db_backed
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine("sqlite:///./sim_scale.db")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        try:
            stats = run_db_backed(session, workers=args.db_workers, seed=args.seed)
        finally:
            session.close()
        print("\nDB-backed:", stats)
        assert stats["completed"] == stats["units"], stats
        assert stats["aggregate_final"] == stats["expected_final"], stats
        print("DB-BACKED OK: real queue drained", stats["workers"], "workers /",
              stats["units"], "units in", round(stats["elapsed_ms"], 1), "ms")

    print("\nSIM-OK: scheduler behavior measured to", f"{max(scales):,}", "nodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
