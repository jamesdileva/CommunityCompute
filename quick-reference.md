# Quick Reference — CommunityCompute

One-page cheat sheet: two-PC setup, everyday commands, env vars, troubleshooting.
Full sprint workflow lives in `AGENTS.md`; history in `worklog.md`.

## Two-PC LAN setup (laptop runs the worker, PC A runs the coordinator)

Prerequisites: both PCs on the **same network** (same WiFi/router is enough —
no internet or port forwarding needed).

```powershell
# --- PC A: check its LAN IP (may change on reboot/DHCP) ---
ipconfig   # look for Wi-Fi IPv4, e.g. 192.168.4.68

# --- PC A: coordinator reachable from the LAN ---
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir apps/coordinator
# NOTE: --host 127.0.0.1 is localhost-only; use 0.0.0.0 for the laptop run.

# --- PC A: one-time firewall rule (Private profile only) ---
New-NetFirewallRule -DisplayName "CommunityCompute" -Direction Inbound `
  -LocalPort 8000 -Protocol TCP -Profile Private -Action Allow

# --- Laptop: Python 3.12+, then ---
pip install httpx psutil pydantic websockets
git clone https://github.com/jamesdileva/CommunityCompute.git
# each PC keeps its OWN identity file automatically (never copy .worker_id*)

# --- Laptop: connectivity check (from the laptop) ---
python scripts/check_lan.py --host 192.168.4.68 --port 8000
# want: resolve OK / tcp connect OK / GET /health -> 200

# --- Laptop: join the pool (background loop: register -> heartbeat -> work) ---
python apps/worker/worker/main.py --coordinator-url http://192.168.4.68:8000 --loop --interval 3

# --- PC A: see both machines, then submit a job ---
# GET http://127.0.0.1:8000/workers            -> 2 workers, capabilities
# POST http://127.0.0.1:8000/jobs
#   {"workload_type":"hello_compute","params":{"op":"sum"},"total_units":40,"chunk_size":1}
# GET http://127.0.0.1:8000/jobs/{id}          -> counts -> completed + aggregate.final
```

## Everyday commands (PC A)

```powershell
# Coordinator (localhost dev)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir apps/coordinator

# Worker: one-shot register | loop | second simulated worker | skip work | slow-work knob
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --once
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --interval 3
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --once --worker-id-file .worker_id_b
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --no-work
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --execution-delay 8

# Submit a job + inspect (PowerShell inline)
python -c "import httpx; print(httpx.post('http://127.0.0.1:8000/jobs', json={'workload_type':'hello_compute','params':{'op':'sum'},'total_units':20,'chunk_size':1}, timeout=5).json()['id'])"
python -c "import httpx; d = httpx.get('http://127.0.0.1:8000/jobs/<id>', timeout=5).json(); print(d['status'], d['counts'], d['aggregate'])"

# Requirements (Sprint 9): only compatible workers claim these units.
# Empty requirements = runs anywhere (incl. workers with no profile).
python -c @"
import httpx
base = 'http://127.0.0.1:8000/jobs'
def sub(reqs, n=1):
    return httpx.post(base, json={'workload_type':'hello_compute','params':{'op':'sum'},
        'total_units':n,'chunk_size':1,'requirements':reqs}, timeout=5).json()['id']
print('cpu  :', sub({'cpu_cores': 4}, 2))
print('ram  :', sub({'ram_mb': 8192}))
print('gpu  :', sub({'gpu': True}))
print('vendor+VRAM:', sub({'gpu': True, 'gpu_vendor': 'amd', 'min_vram_mb': 3000}))
print('runtime:', sub({'runtime': 'hello_compute'}))
print('os   :', sub({'os': 'Windows'}))
"@
# unknown requirement keys are rejected 422 (typos fail loudly at submit)
# Worker tiers + compatibility explanations (Sprint 10)
# GET /workers/{id}                    -> tiers {gpu, cpu, ram} = H1/H2/H3 or unknown
# GET /jobs/{id}/compatibility/{wid}   -> {compatible, reason, checks:[{dimension,need,have,passed}]}
python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/workers/<wid>', timeout=5).json()['tiers'])"

# Hardware tiers (per resource axis, architecture §5)
#   GPU  : <=4GB or integrated/undetected -> H1 · 4-12GB -> H2 · >12GB -> H3 (best GPU wins)
#   CPU  : <=4 physical cores -> H1 · 5-8 -> H2 · >8 -> H3 (falls back to logical)
#   RAM  : <=8GB -> H1 · 16-32GB -> H2 · >32GB -> H3
# Prototype: PC A RX 6400 4GB = gpu H1, cpu H2, ram H2; Iris Xe laptop = all H1

# Job with duplicate verification (fraction 0..1 double-executed by a 2nd worker)
python -c "import httpx; print(httpx.post('http://127.0.0.1:8000/jobs', json={'workload_type':'hello_compute','params':{'op':'sum'},'total_units':2,'chunk_size':1,'verify_sample':1.0}, timeout=5).json()['id'])"
# corrupted results -> 422 with failure_kind: value_mismatch | hash_mismatch |
# worker_error | unsupported_workload | verification_disagreement

# Tests (always before commit)
python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly
python -m pytest apps/coordinator/tests apps/worker/tests           # + random order
python -m pytest apps/coordinator/tests/test_leasing.py -v          # single file

# Baselines + LAN
python scripts/collect_baseline.py --out docs/baseline-<hostname>.json
python scripts/check_lan.py --host 192.168.4.68 --port 8000

# Dev DB reset (prototype: disposable; additive bootstrap covers added columns,
# but removed constraints — e.g. Sprint 8's dropped (job,seq) unique — need a reset)
Remove-Item communitycompute.db -ErrorAction SilentlyContinue
sqlite3 communitycompute.db ".tables"                               # workers work_units results ...

# Cleanup stray background workers/coordinators
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## Env vars (`.env`, never committed — see `.env.example`)

| Var | Default | Used by |
| --- | ------- | ------- |
| `COORDINATOR_URL` | `http://127.0.0.1:8000` | worker |
| `DATABASE_URL` | `sqlite:///./communitycompute.db` | coordinator |
| `HEARTBEAT_TIMEOUT_SECONDS` | `60` | coordinator offline detection |
| `LEASE_DURATION_SECONDS` | `60` | coordinator lease expiry |
| `WORKER_ID_FILE` | `.worker_id` | worker identity |
| `LOG_LEVEL` | `info` | coordinator |

## Sprint workflow (per AGENTS.md)

Plan → Scope (confirm with user) → Implement → Verify (`pytest` + live)
→ Commit (`feat(sprint-N): ...`) → Push → append `worklog.md`.

## Troubleshooting

- **Port 8000 busy**: cleanup commands above, then restart.
- **Laptop can't connect**: coordinator bound to `127.0.0.1`? (needs `0.0.0.0`);
  wrong LAN IP? (re-run `ipconfig`); firewall rule present?
- **Console crash `charmap ... U+2192`**: never print `→`/`—`/§ from worker
  console code (docstrings are safe) — use `->`/`-`.
- **Weird DB errors after update**: delete the dev DB (prototype rule).
- **Worker stuck "register FAILED"**: coordinator down or wrong URL; Ctrl+C
  stops the loop cleanly.
