"""Collect hardware baseline (Sprint 3).

Delegates to the worker's shared capability-discovery module — the same
implementation the running worker uses to report. No manual hardware entry
allowed (roadmap Sprint 3 rule): this script is the source of truth.

Usage:
    python scripts/collect_baseline.py [--out docs/baseline-<hostname>.json]
"""

from __future__ import annotations

import argparse
import json
import platform
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "worker"))

from worker.capabilities.discover import discover_capabilities  # noqa: E402


def build_baseline() -> dict:
    """Baseline envelope around the auto-discovered capability profile."""
    profile = discover_capabilities()
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "python": platform.python_version(),
        **profile.model_dump(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Collect hardware baseline (Sprint 3)")
    p.add_argument("--out", default=None, help="Write JSON baseline to file")
    args = p.parse_args(argv)

    baseline = build_baseline()
    text = json.dumps(baseline, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
