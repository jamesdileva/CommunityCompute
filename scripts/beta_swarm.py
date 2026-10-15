"""Mocked private-beta swarm (Sprint 26 exit proof, single machine).

Spins N isolated worker processes (separate IDs, policies, caches, logs),
kills one mid-job, pauses + resumes another, then asserts the job completes
— purely through public APIs, with zero manual database intervention.

Usage:
    python scripts/beta_swarm.py [--workers 3] [--units 12] [--base-url URL]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_MAIN = REPO_ROOT / "apps" / "worker" / "worker" / "main.py"


def log(*parts: object) -> None:
    print("[swarm]", *parts, flush=True)


def start_worker(home: Path, base_url: str, interval: float = 2.0,
                 extra: list[str] | None = None) -> subprocess.Popen:
    cmd = [sys.executable, str(WORKER_MAIN), "--coordinator-url", base_url,
           "--loop", "--interval", str(interval), "--no-ws",
           "--worker-id-file", str(home / ".worker_id"),
           "--log-file", str(home / "worker.log")]
    cmd += extra or []
    log("starting", home.name, " ".join(extra or []))
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mocked beta swarm (Sprint 26)")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--units", type=int, default=12)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    tmp = Path(tempfile.mkdtemp(prefix="beta-swarm-"))
    procs: dict[str, subprocess.Popen] = {}
    try:
        for i in range(args.workers):
            home = tmp / f"pc{i + 1}"
            home.mkdir()
            procs[f"pc{i + 1}"] = start_worker(home, base)
        time.sleep(6)  # let everyone register + report
        workers = httpx.get(f"{base}/workers", timeout=5).json()
        log(f"{len(workers)} workers joined:",
            [(w["id"][:8], w["status"]) for w in workers])
        assert len(workers) == args.workers, "not all workers joined"

        job = httpx.post(
            f"{base}/jobs",
            json={"workload_type": "hello_compute", "params": {"op": "sum"},
                  "total_units": args.units, "chunk_size": 1},
            timeout=5,
        ).json()["id"]
        log("job", job[:8], f"submitted ({args.units} units)")
        time.sleep(4)

        victim = "pc2" if "pc2" in procs else sorted(procs)[0]
        log(f"killing {victim} mid-job (leave/fail simulation)")
        procs[victim].terminate()
        procs[victim].wait(timeout=10)
        del procs[victim]

        if "pc3" in procs:
            wid = _worker_id(tmp / "pc3")
            httpx.post(f"{base}/workers/{wid}/pause", timeout=5)
            log("pc3 paused via dashboard (operator action)")
            time.sleep(4)
            httpx.post(f"{base}/workers/{wid}/resume", timeout=5)
            log("pc3 resumed")

        deadline = time.time() + 90
        while time.time() < deadline:
            time.sleep(3)
            detail = httpx.get(f"{base}/jobs/{job}", timeout=5).json()
            log("job:", detail["status"], detail["counts"])
            if detail["status"] == "completed":
                break
        assert detail["status"] == "completed", detail
        assert detail["aggregate"]["final"] == sum(range(1, args.units + 1))
        summary = httpx.get(f"{base}/network/summary", timeout=5).json()
        capacity = httpx.get(f"{base}/network/capacity", timeout=5).json()
        log("summary:", json.dumps(summary["workers"]),
            "completed_5m:", summary["completed_last_5m"])
        log("capacity: online:", capacity["online_workers"],
            "cores:", capacity["cpu_cores"], "queue:", capacity["queued_units"])
        log("SWARM-OK: join/leave/fail/reconnect handled without DB intervention")
        return 0
    finally:
        for name, proc in procs.items():
            if proc.poll() is None:
                proc.terminate()
        log(f"homes kept at {tmp} for inspection")


def _worker_id(home: Path) -> str:
    return (home / ".worker_id").read_text(encoding="utf-8").strip()


if __name__ == "__main__":
    sys.exit(main())
