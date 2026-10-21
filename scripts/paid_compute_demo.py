"""Sprint 37 exit proof: a controlled customer pays for work, and the system
calculates contributor/network compensation.

Runs against a live coordinator using only the public customer API and a real
worker:

    create customer -> top-up (simulated provider) -> submit prepaid job
    -> worker --loop executes -> assert:
         charged == contributor + network, both shares > 0,
         customer balance == top-up - charged, job completed.

No real money moves: the only payment provider is ``simulated`` (AGENTS.md
non-goals: no real-money payouts). Exit code 0 only when every assertion holds.

    python scripts/paid_compute_demo.py --coordinator-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Documented steps the proof exercises, in order (docs/pricing.md).
DOCUMENTED_STEPS = [
    "operator mints a customer API key",
    "customer tops up the prepaid balance (simulated provider)",
    "customer submits a prepaid job",
    "workers execute; verified originals earn contributor compensation",
    "operator/customer can read the charge and the contributor/network split",
]


def _auth(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def _request(method: str, url: str, payload: dict | None = None,
             token: str | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", **_auth(token)}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _try_get(url: str, token: str | None = None) -> dict | None:
    try:
        return _request("GET", url, token=token)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None


def summarize(job: dict | None, billing: dict | None, earnings: dict | None,
              network: dict | None, topup_cents: int) -> dict:
    """Verdict for the exit condition from public API views."""
    charged = int((billing or {}).get("lifetime_charged_cents", 0))
    balance = int((billing or {}).get("balance_cents", 0))
    contributor = int((earnings or {}).get("balance_cents", 0))
    network_fee = int((network or {}).get("network_cents", 0))
    completed = bool(job) and job.get("status") == "completed"
    split_ok = charged > 0 and contributor + network_fee == charged
    funded_ok = balance == topup_cents - charged
    return {
        "job_completed": completed,
        "charged_cents": charged,
        "contributor_cents": contributor,
        "network_cents": network_fee,
        "split_ok": split_ok,
        "customer_balance_cents": balance,
        "funded_ok": funded_ok,
        "ok": (
            completed and split_ok and funded_ok
            and contributor > 0 and network_fee > 0
        ),
    }


def render(summary: dict, topup_cents: int) -> str:
    def mark(ok: bool) -> str:
        return "yes" if ok else "NO"

    return "\n".join([
        "paid-compute proof (simulated money)",
        f"  job completed        : {mark(summary['job_completed'])}",
        f"  customer charged     : {summary['charged_cents']} cents (funded {topup_cents})",
        f"  contributor earned   : {summary['contributor_cents']} cents",
        f"  network fee          : {summary['network_cents']} cents",
        f"  split sums to charge : {mark(summary['split_ok'])}",
        (
            f"  customer balance     : {summary['customer_balance_cents']} cents "
            f"({mark(summary['funded_ok'])})"
        ),
        f"  exit condition met   : {mark(summary['ok'])}",
    ])


def _worker_cmd(worker_exe: str | None) -> list[str]:
    if worker_exe:
        return [worker_exe]
    return [sys.executable, str(REPO_ROOT / "apps" / "worker" / "worker" / "main.py")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sprint 37 paid-compute proof")
    parser.add_argument("--coordinator-url", default="http://127.0.0.1:8000")
    parser.add_argument("--customer-name", default="paid-compute-demo")
    parser.add_argument("--topup-cents", type=int, default=100)
    parser.add_argument("--units", type=int, default=4)
    parser.add_argument("--duration", type=float, default=60.0,
                        help="max seconds to observe completion")
    parser.add_argument("--worker-exe", default=None)
    parser.add_argument("--work-dir", default=None)
    args = parser.parse_args(argv)
    if args.units <= 0:
        print("ERROR: --units must be positive", file=sys.stderr)
        return 2

    base = args.coordinator_url.rstrip("/")
    work_dir = Path(args.work_dir) if args.work_dir else Path(
        tempfile.mkdtemp(prefix="cc-paid-")
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    id_file = work_dir / ".worker_id"
    env = {**os.environ, "WORKER_ID_FILE": str(id_file)}

    print(f"coordinator: {base}")
    print(f"work dir   : {work_dir}")
    print(f"steps      : {' -> '.join(DOCUMENTED_STEPS)}")

    print("\n[1/5] operator mints a customer")
    customer = _request("POST", f"{base}/api/v1/customers",
                        {"name": args.customer_name})
    token = customer["api_key"]

    print(f"[2/5] customer tops up {args.topup_cents} cents (simulated provider)")
    topup = _request("POST", f"{base}/api/v1/billing/topup",
                     {"amount_cents": args.topup_cents}, token=token)
    print(f"      payment {topup['payment_id']} -> balance {topup['balance_cents']} cents")

    print(f"[3/5] submit a {args.units}-unit prepaid job")
    job = _request("POST", f"{base}/api/v1/jobs", {
        "workload_type": "hello_compute",
        "params": {"op": "sum"},
        "total_units": args.units,
        "chunk_size": 1,
    }, token=token)
    print(f"      job {job['id']} charged upfront")

    print("[4/5] worker --loop (executing paid work)")
    loop = subprocess.Popen(
        _worker_cmd(args.worker_exe) + [
            "--coordinator-url", base, "--loop", "--interval", "1",
            "--heartbeat-interval", "5", "--no-ws",
            "--worker-id-file", str(id_file),
            "--work-root", str(work_dir / "work"),
        ],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    summary = summarize(None, None, None, None, args.topup_cents)
    deadline = time.time() + args.duration
    try:
        while time.time() < deadline:
            state = _try_get(f"{base}/api/v1/jobs/{job['id']}", token=token)
            billing = _try_get(f"{base}/api/v1/billing", token=token)
            network = _try_get(f"{base}/billing/network")
            worker_id = (
                id_file.read_text(encoding="utf-8").strip()
                if id_file.exists() else ""
            )
            earnings = (
                _try_get(f"{base}/workers/{worker_id}/earnings")
                if worker_id else None
            )
            summary = summarize(state, billing, earnings, network, args.topup_cents)
            if summary["ok"]:
                break
            time.sleep(1.0)
    finally:
        loop.terminate()
        try:
            loop.wait(timeout=10)
        except subprocess.TimeoutExpired:
            loop.kill()

    print("\n[5/5] verify charge split")
    print(render(summary, args.topup_cents))
    if not summary["ok"]:
        print("\nworker log tail:")
        assert loop.stdout is not None
        print(loop.stdout.read()[-2000:])
        return 1
    print("\npaid compute works: customer charged, contributor paid, network fee taken.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
