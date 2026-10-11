"""Minimal Worker process for Sprint 0.

Proves: PC ──> Coordinator (exit condition, localhost now; LAN with --coordinator-url).

Usage:
    python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --once
    python apps/worker/worker/main.py --coordinator-url http://192.168.4.68:8000 --loop --interval 15

Sprint 2 will add: startup sequence, registration POST, shutdown handling.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow direct execution: `python apps/worker/worker/main.py` (adds apps/worker to sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from worker.config import get_coordinator_url, get_or_create_worker_id, get_worker_id_file


def ping_coordinator(coordinator_url: str, worker_id: str, timeout: float = 5.0) -> dict:
    """GET /health on the coordinator. Raises on connection/HTTP failure."""
    url = f"{coordinator_url.rstrip('/')}/health"
    resp = httpx.get(url, timeout=timeout, headers={"X-Worker-Id": worker_id})
    resp.raise_for_status()
    return resp.json()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CreatorLab minimal worker (Sprint 0 ping)")
    p.add_argument("--coordinator-url", default=None, help="Coordinator base URL")
    p.add_argument("--worker-id-file", default=None, help="Persistent worker ID file")
    p.add_argument("--once", action="store_true", help="Ping once and exit")
    p.add_argument("--loop", action="store_true", help="Ping in a loop (heartbeat precursor)")
    p.add_argument("--interval", type=float, default=15.0, help="Loop interval seconds")
    p.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout seconds")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    coordinator_url = get_coordinator_url(args.coordinator_url)
    worker_id = get_or_create_worker_id(get_worker_id_file(args.worker_id_file))
    print(f"[worker {worker_id}] coordinator: {coordinator_url}", flush=True)

    def once() -> int:
        try:
            body = ping_coordinator(coordinator_url, worker_id, timeout=args.timeout)
        except Exception as exc:  # noqa: BLE001 — Sprint 0 diagnostics, refined later
            print(f"[worker {worker_id}] ping FAILED: {exc}", flush=True)
            return 1
        print(f"[worker {worker_id}] ping OK: {body}", flush=True)
        return 0

    if args.loop and not args.once:
        print(f"[worker {worker_id}] loop every {args.interval}s (Ctrl+C to stop)", flush=True)
        try:
            while True:
                once()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print(f"[worker {worker_id}] stopped", flush=True)
            return 0
        return 0
    return once()


if __name__ == "__main__":
    sys.exit(main())
