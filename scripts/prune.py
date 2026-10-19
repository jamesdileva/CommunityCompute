"""Retention enforcement driver (Sprint 35).

Ages out data older than the retention windows. **Dry run by default** --
pass `--apply` to actually delete. Reads the coordinator's own database (no
server required). See `docs/data-retention.md`.

Usage:
    python scripts/prune.py                          # dry run, default windows
    python scripts/prune.py --apply                  # enforce
    python scripts/prune.py --work-days 14 --apply
    python scripts/prune.py --financial-days 180 --apply
    python scripts/prune.py --database-url sqlite:///./communitycompute.db --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "coordinator"))


def main() -> int:
    parser = argparse.ArgumentParser(description="CommunityCompute retention pruner (Sprint 35)")
    parser.add_argument("--database-url", default=None, help="override DATABASE_URL")
    parser.add_argument("--telemetry-days", type=int, default=None,
                        help="heartbeats + resource samples window (default: settings)")
    parser.add_argument("--work-days", type=int, default=None,
                        help="terminal units/results/attempts/tokens window")
    parser.add_argument("--financial-days", type=int, default=None,
                        help="contribution records + credit ledger window (0 = keep forever)")
    parser.add_argument("--apply", action="store_true",
                        help="actually delete (default is a dry run)")
    parser.add_argument("--json", default=None, help="also write the report JSON here")
    args = parser.parse_args()

    if args.database_url:
        import os
        os.environ["DATABASE_URL"] = args.database_url

    from app.config import get_settings
    get_settings.cache_clear()
    from app.db import SessionLocal, init_db
    from app.services import retention

    init_db()
    settings = get_settings()

    db = SessionLocal()
    try:
        report = retention.prune(
            db,
            telemetry_days=(
                args.telemetry_days if args.telemetry_days is not None
                else settings.retention_telemetry_days
            ),
            work_days=(
                args.work_days if args.work_days is not None
                else settings.retention_work_days
            ),
            financial_days=(
                args.financial_days if args.financial_days is not None
                else settings.retention_financial_days
            ),
            apply=args.apply,
        )
    finally:
        db.close()

    mode = "APPLIED" if report["applied"] else "DRY RUN (pass --apply to delete)"
    print(f"retention {mode} as of {report['as_of']}")
    print(f"windows: telemetry={report['windows']['telemetry_days']}d "
          f"work={report['windows']['work_days']}d "
          f"financial={report['windows']['financial_days']}d")
    for table, count in report["deleted"].items():
        print(f"  {table:26} {count}")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
