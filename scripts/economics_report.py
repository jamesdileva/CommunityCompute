"""Cost-per-useful-compute report driver (Sprint 34).

Reads the coordinator's own database (no server required) and prints the
measured economics model: units, execution time, uptime, utilization, and the
verification overhead, combined with clearly-labelled cost assumptions
(electricity price, hardware power/price/life, bandwidth, infrastructure, and
centralized list prices). All assumption inputs can be overridden on the CLI.

Usage:
    python scripts/economics_report.py
    python scripts/economics_report.py --json out.json
    python scripts/economics_report.py --electricity 0.30 --utilization 0.5
    python scripts/economics_report.py --database-url sqlite:///./communitycompute.db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "coordinator"))


def main() -> int:
    parser = argparse.ArgumentParser(description="CommunityCompute economics report (Sprint 34)")
    parser.add_argument("--database-url", default=None,
                        help="override DATABASE_URL (default: settings)")
    parser.add_argument("--electricity", type=float, default=None,
                        help="electricity price USD/kWh (assumption)")
    parser.add_argument("--bandwidth", type=float, default=None,
                        help="bandwidth USD/GB (assumption)")
    parser.add_argument("--infra", type=float, default=None,
                        help="infrastructure USD/month (assumption)")
    parser.add_argument("--utilization", type=float, default=None,
                        help="utilization 0..1 to use when none is measured (assumption)")
    parser.add_argument("--json", default=None, help="also write the full report JSON here")
    args = parser.parse_args()

    if args.database_url:
        import os
        os.environ["DATABASE_URL"] = args.database_url

    from app.config import get_settings
    get_settings.cache_clear()
    from app.db import SessionLocal, init_db
    from app.economics.report import build_report, format_report

    init_db()
    overrides = {
        "electricity_usd_per_kwh": args.electricity,
        "bandwidth_usd_per_gb": args.bandwidth,
        "infra_usd_per_month": args.infra,
        "assumed_utilization": args.utilization,
    }
    db = SessionLocal()
    try:
        report = build_report(db, get_settings(), **overrides)
    finally:
        db.close()

    print(format_report(report))
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
