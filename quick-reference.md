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

# Contributor policy (Sprint 11): policy.json beside the worker id file
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --pause     # stop accepting
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --resume    # accept again
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --policy-file mypol.json
# Example policy.json (all optional; unknown signals fail closed):
# {
#   "idle_only": true, "idle_threshold_seconds": 180,
#   "max_cpu_percent": 80, "max_gpu_percent": 50,
#   "temperature_ceiling_c": 70, "battery_policy": "plugged_only",
#   "allowed_hours": {"start_hour": 9, "end_hour": 23, "days": [0,1,2,3,4]}
# }
# → paused workers report available:false in heartbeats; GET /workers shows "paused"

# Telemetry + throttling (Sprint 12): one sample per tick; policy re-read each tick
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --interval 2 --heartbeat-interval 20
# GET /workers/{id}            -> status: online | throttled | paused | offline

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

# Dashboard (Sprint 16): run after the coordinator is up; Contributor + Network tabs
cd apps/dashboard
npm run dev      # -> http://127.0.0.1:5173 (5s auto-refresh)
# Pause button is ENFORCEMENT: a paused worker gets no work claims
# (worker-side control remains --pause/--resume + policy.json)

# Control socket (Sprint 17): automatic in --loop (WS /ws/worker/{id}); job submits
# push work_available so the worker ticks immediately instead of sleeping out --interval
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --interval 30  # still claims in ~1-2s
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --no-ws        # disable: HTTP heartbeat + plain polling
# Heartbeats ride the socket while connected, HTTP POST when down (never both).
# Operator pause/resume also pushes a pause/resume frame down the socket.

# TLS internet prototype (Sprint 19): coordinator serves TLS, worker dials out (no inbound ports)
python scripts/gen_dev_cert.py --out dev-tls   # dev self-signed cert (openssl/cryptography); NOT for production
python -m uvicorn app.main:app --host 127.0.0.1 --port 8443 --app-dir apps/coordinator --ssl-certfile dev-tls.pem --ssl-keyfile dev-tls.key
python apps/worker/worker/main.py --coordinator-url https://127.0.0.1:8443 --ca-bundle dev-tls.pem --loop
# --insecure skips verification (dev LAN only, prints a warning). Real deployments use a
# proper CA or a private network/VPN (see implementation-guide); worker auth lands in Sprint 20.
# Remote logging = coordinator logs (uvicorn access + worker heartbeats/results, incl. WS peer IP).

# Worker authentication (Sprint 20): AUTH_ENABLED=true on the coordinator locks
# every worker-facing route (register/heartbeat/capabilities/claim/result/resources/WS)
# behind bearer credentials. Default false = anonymous LAN dev flow (unchanged).
# 1. operator mints a single-use enrollment token:
#    POST /auth/enrollment-tokens {"note": "laptop"} -> {"token": "...", ...} (shown once)
# 2. worker exchanges it for its long-lived credential (saved to credential.json):
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --enroll <enrollment-token>
# 3. from then on the worker sends Authorization: Bearer on HTTP + ?token= on the socket
# Operator: POST /workers/{id}/revoke (immediate lockout), POST .../rotate-credential,
# GET /workers/{id}/credentials + GET /auth/credentials (auditing, no hashes).
# Stored form is sha256-only: a DB leak yields no usable tokens.

# Security boundary (Sprint 21): submit allowlist + sealed assignments + worker refusal
# POST /jobs with unknown workload_type -> 422 (nothing persisted, audit-visible)
# every claim carries manifest_signature (HMAC over unit id/type/range/params);
# the worker verifies before executing and refuses tampered units outright.
# WORKLOAD_SIGNING_KEY must match on both sides (dev default warns loudly at startup).
# per-unit temp work dirs under --work-root (default <idfile-dir>/work), always cleaned;
# execute() runs under --unit-time-limit (default 300s).

# Worker packaging (Sprint 24): install without a dev environment
# 1. new machine: python apps/worker/worker/main.py --setup   (or the bundle's worker.exe --setup)
python apps/worker/worker/main.py --setup
# 2. build the bundle (needs: pip install pyinstaller pyside6): scripts/build_worker.ps1
#    -> dist/worker/worker.exe (one-dir console build; ~190MB with Qt)
# 3. run it: worker.exe --loop  |  tray mode: worker.exe --loop --tray
# 4. autostart: worker.exe --install-autostart / --remove-autostart (HKCU Run, no elevation)
# 5. update check only: worker.exe --check-update  (exit 2 = newer coordinator)
# 6. logs: worker.exe --loop --log-file worker.log  (rotating 1MB x3)
# 7. uninstall: scripts/uninstall_worker.ps1  (stops worker, removes autostart, optional data wipe)
# Privacy: docs/privacy.md (what's sent, what's never touched, how to leave)

# Contributor experience (Sprint 25): onboarding chain + one-screen status
# --setup now runs: coordinator -> identity -> HARDWARE SCAN -> capability estimate
#   -> full policy (idle/cpu/gpu/temp/battery/hours/bandwidth) -> autostart -> join
python apps/worker/worker/main.py --setup
# --status: am I contributing? (id, reachability, participation, limits, cache, sandbox)
python apps/worker/worker/main.py --status
# Contributor tab shows each worker's limits read-only (from capabilities.policy_summary);
# limits are edited locally (policy.json / --setup), never pushed from the server.

# Sandboxed execution (Sprint 22, Windows, opt-in): Job Object limits + low-integrity child
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --sandbox
# --sandbox runs each unit in a child process: memory/process caps + kill-on-close
# (Job Object, always on); low-integrity write-denial needs elevation and is
# reported honestly per run ("job-object-only" vs "job-object + low-integrity").
# Without elevation there is NO kernel read/network denial — AppContainer profile
# API is absent from Win11 Home; containers would need Docker (not installed).

# Reputation (Sprint 23): reliability is derived from conduct, never stored
# GET /workers/{id}/reputation -> {score, rated, outcomes, accepted/rejected/
#   expired/agreed/disagreed, rejections_by_kind, recent}
# score = Laplace-smoothed success rate; unrated until 5 scored outcomes.
# every accepted/rejected result, expired lease, and duplicate agree/disagree
# is recorded; lying workers sink toward 0 while honest ones rise.

# Accounting (Sprint 27): auditable per-unit contribution ledger
# GET /accounting/entries[?job_id=&worker_id=&limit=] -> [{unit, job, worker,
#   workload, execution/cpu/gpu ms, verified, verified_by, voided_at}]
# GET /workers/{id}/accounting -> {units_completed/valid/voided, totals ms,
#   verified_units, availability_24h, reliability score}
# v1 estimates: cpu = wall time (single-threaded compute); gpu = wall time
# iff the job required a GPU, else 0. Overturns void records (history kept).

# Compute credits (Sprint 28): earn by contributing, spend by consuming
# +1 per verified original unit (duplicates/failures/self-deals earn nothing);
# -1 per unit upfront when a job names submitter_worker_id (absent = free pool).
# GET /workers/{id}/credits -> {balance, earned, spent}
# GET /credits/ledger[?worker_id=&limit=] -> [{amount, reason, job_id, unit,...}]
# Insufficient balance -> 402 {error, need, have}; no refunds v1 (failed units
# still cost scheduling). Balance is always SUM(amount) - never stored.

# Customer API (Sprint 29): programmatic compute access at /api/v1 - no dashboard
# Operator (unauthenticated in prototype, like /auth/enrollment-tokens):
#   POST /api/v1/customers {name} -> {id, api_key}   (raw key shown once)
#   GET  /api/v1/customers | /api/v1/keys
#   POST /api/v1/customers/{id}/rotate-key | /revoke
# Customer (Authorization: Bearer <api_key>; own jobs only, else 404):
#   POST /api/v1/jobs {workload_type, params, total_units, chunk_size,
#                      verify_sample, requirements} -> {id, status,...}
#   GET  /api/v1/jobs/{id}            -> status + per-unit counts + aggregate
#   GET  /api/v1/jobs/{id}/results    -> per-unit values/hashes/failure_kind
#   GET  /api/v1/usage               -> {jobs, units, units_by_status/workload}
# Free community pool: customer jobs charge no credits (architecture 21).

# Customer isolation + quotas (Sprint 30)
#   GET /api/v1/me                     -> {customer_id, name, status}
#   GET /api/v1/jobs                   -> own jobs only (JobSummary[])
#   GET /api/v1/workloads              -> signed workload manifests (catalog)
#   GET /api/v1/quota                  -> caps + live usage
# Per-customer caps (env CUSTOMER_MAX_UNITS_PER_JOB / _IN_FLIGHT_JOBS /
# _UNITS_IN_FLIGHT) enforced at POST /api/v1/jobs: over units-per-job -> 413,
# over in-flight jobs/units -> 429. Jobs record workload_version + isolation_scope;
# every assignment carries a signed workload definition the worker re-verifies
# (fail closed on version mismatch / bad signature). Cross-tenant reads -> 404.

# Two workload types through the same scheduler (Sprint 13; no branching)
python -c @"
import httpx
b = 'http://127.0.0.1:8000/jobs'
def sub(t, p, n):
    return httpx.post(b, json={'workload_type': t, 'params': p,
        'total_units': n, 'chunk_size': 1}, timeout=5).json()['id']
print('hello_compute:', sub('hello_compute', {'op': 'sum'}, 4))
print('stats_range  :', sub('stats_range', {}, 3))
"@
# First AI workload (Sprint 14): deterministic embeddings over a synthetic corpus
python -c @"
import httpx
jid = httpx.post('http://127.0.0.1:8000/jobs', json={'workload_type': 'embeddings',
    'params': {'dim': 64}, 'total_units': 40, 'chunk_size': 10}, timeout=5).json()['id']
print('embeddings  :', jid)
"@
# embedder is adapter-based (worker/execution/embeddings/embedder.py): a model-backed
# embedder replaces HashingEmbedder behind the same signature (model cache: Sprint 15)

# Model cache (Sprint 15): fetch-once + verify + reuse; scheduler prefers cache-warm
# submit with requirements {"model": "hashing-embedder@1"} -> first unit fetches,
# rest reuse (metrics.cache_hit 0 -> 1); GET /workers shows capabilities.cached_models
python -c @"
import httpx
print(httpx.post('http://127.0.0.1:8000/jobs', json={'workload_type': 'embeddings',
    'params': {'dim': 32}, 'total_units': 20, 'chunk_size': 10,
    'requirements': {'model': 'hashing-embedder@1'}}, timeout=5).json()['id'])
"@
# cache dir: <idfile-dir>/models (override: --model-cache-dir / MODEL_CACHE_DIR)
# GET /workers/{id} -> capabilities.runtimes lists what the worker can execute
# GET /workers/{id}            -> status: online | throttled | paused | offline
# GET /workers/{id}/resources  -> newest telemetry samples (cpu %, ram, gpu %, vram, temp)

# Worker tiers + compatibility explanations (Sprint 10)
# GET /workers/{id}                    -> tiers {gpu, cpu, ram} = H1/H2/H3 or unknown
# GET /jobs/{id}/compatibility/{wid}   -> {compatible, reason, checks:[...], score:{...}}
python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/workers/<wid>', timeout=5).json()['tiers'])"

# Scheduling score (Sprint 31): among *compatible* units, the worker claims the
# highest score; FIFO (created_at, sequence) breaks ties. Set SCORING_ENABLED=false
# for plain FIFO. Components (architecture §10), each in the /compatibility score:
#   + capability_fit  (headroom on the axes the job needs)
#   + estimated_speed (1/(1+historical_ms/ref) for this worker)
#   + cached_model    (1 when the job's model is already local)
#   + reliability     (reputation; unrated -> neutral 0.5)
#   + availability    (idle load x lease headroom)
#   - transfer_cost   (payload + uncached model bytes, normalized)
#   - location_penalty(0 unless job.location and worker.location disagree)
# Weights/refs are SCORING_WEIGHT_* / SCORING_REFERENCE_* settings.

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

# Large-scale simulation (Sprint 32): streams synthetic nodes, runs the REAL
# compat+scoring on a bounded sample, and validates the real DB/queue at small N.
python scripts/simulate_scale.py                       # 100 -> 100,000
python scripts/simulate_scale.py --include-1m --sample 4000   # + 1,000,000
python scripts/simulate_scale.py --scales 100,1000 --db-workers 200
# engine: app/simulation/ (make_workers streams O(1) memory; simulate_scale,
# run_db_backed). Synthetic attrs: GPU/VRAM, CPU, RAM, bandwidth, availability,
# reliability, location, model cache. Safe on a laptop: no node is persisted
# or spawned except the opt-in small DB-backed run.

# Multi-workload network (Sprint 33): the first GPU-gated workload. Its
# definition requires {"gpu": true, "min_vram_mb": 2048}, so only GPU-class
# workers can claim it while CPU workloads run elsewhere through one scheduler.
python -c @"
import httpx
print(httpx.post('http://127.0.0.1:8000/jobs', json={'workload_type': 'image_generate',
    'params': {'size': 16}, 'total_units': 4, 'chunk_size': 1,
    'requirements': {'gpu': True, 'min_vram_mb': 2048}}, timeout=5).json()['id'])
"@
# deterministic tile checksums (pure-Python stub; no AI runtime bundled) so the
# coordinator re-derives and verifies exactly. Executor: worker/execution/image_generate.py.
# GET /api/v1/workloads now lists 4 signed types; a CPU-only worker's claim on
# this job returns {} (excluded by the gpu requirement).

# Economics research (Sprint 34): measured cost-per-useful-compute model over
# real coordinator data (execution time, verification overhead, uptime, classes)
# vs cited centralized list prices. See docs/economics.md for the findings.
python scripts/economics_report.py                     # human-readable report
python scripts/economics_report.py --json report.json  # machine-readable
python scripts/economics_report.py --electricity 0.30 --utilization 0.5 --infra 60
# or with the coordinator running: GET http://127.0.0.1:8000/economics/report
# model: app/economics/{model,measure,report}.py; costs are ASSUMED (electricity,
# hardware amortization, bandwidth, infra) while volume/time/overhead are MEASURED.
# Headline = utilization-adjusted cost per useful machine-hour; sensitivity grid
# over electricity price x utilization shows where owned hardware beats cloud.

# Public-beta readiness (Sprint 35): the roadmap checklist as live data, plus
# a documented go/no-go decision (docs/public-beta-readiness.md) -- currently
# NO-GO for open enrollment / GO for an invited, allowlisted beta.
#   GET  http://127.0.0.1:8000/beta/readiness
# Data retention (dry-run by default; never automatic):
python scripts/prune.py                          # count what would be removed
python scripts/prune.py --apply                  # enforce (telemetry 7d, work 30d)
python scripts/prune.py --work-days 14 --financial-days 180 --apply
#   POST /beta/prune           (dry run)
#   POST /beta/prune?apply=true
# review docs: docs/security-review.md, docs/incident-response.md,
#   docs/terms.md, docs/data-retention.md, docs/public-beta-readiness.md

# Public community network (Sprint 36): discover -> download -> install ->
# configure -> join -> receive work -> earn credit, no developer help.
# 1. static onboarding website (no build step; plain HTML/CSS/JS):
python scripts/serve_website.py                  # http://127.0.0.1:8080
python scripts/serve_website.py --port 9000
#    loads the live catalog from a coordinator: ?api=http://<coord>:8000
#    (also editable on the page; remembered in localStorage)
# 2. public read-only workload catalog (no auth; human-readable contract):
#    GET http://127.0.0.1:8000/workloads  -> [{name, version, description,
#      params, requirements, gpu}]  (signed manifests stay at /api/v1/workloads)
# 3. contributor dashboard: "My node" tab (status, live resources, credits
#    earned/spent, reliability, current work); operator tab renamed "Workers".
#    cd apps/dashboard; npm run dev                 # http://127.0.0.1:5173
# 4. participant docs: docs/getting-started.md, docs/support.md
# 5. exit proof (automates the documented journey end to end):
python scripts/onboard_participant.py --coordinator-url http://127.0.0.1:8000 --mint
#    -> mints a token, runs --setup -> --enroll -> --loop, submits a job, and
#       asserts joined + received_work + earned_credit (exit 0 only when all).
#    bundle path: --worker-exe dist/worker/worker.exe
#    participant flow (token from operator): --token <enrollment-token>

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
| `MIN_WORKER_VERSION` | `` (off) | claim gate: outdated workers get 426, no new work |
| `MAX_LEASES_PER_WORKER` | `8` | anti-hoarding: simultaneous leases per worker |
| `ECONOMICS_ELECTRICITY_USD_PER_KWH` | `0.17` | economics model (Sprint 34) |
| `ECONOMICS_BANDWIDTH_USD_PER_GB` | `0.0` | economics model |
| `ECONOMICS_TRANSFER_MB_PER_UNIT` | `1.0` | economics model |
| `ECONOMICS_INFRA_USD_PER_MONTH` | `40.0` | economics model |
| `ECONOMICS_ASSUMED_UTILIZATION` | `0.30` | economics model (fallback when unmeasured) |
| `ECONOMICS_CLOUD_GPU_USD_PER_HOUR` | `0.53` | economics baseline (T4-class) |
| `ECONOMICS_CLOUD_CPU_USD_PER_HOUR` | `0.032` | economics baseline (vCPU) |
| `ECONOMICS_HARDWARE_CLASSES` | `` (built-in) | economics JSON override for class table |
| `ECONOMICS_CLOUD_BASELINES` | `` (built-in) | economics JSON override for baselines |
| `RETENTION_TELEMETRY_DAYS` | `7` | retention: heartbeats + samples window (Sprint 35) |
| `RETENTION_WORK_DAYS` | `30` | retention: terminal units/results/attempts/tokens |
| `RETENTION_FINANCIAL_DAYS` | `0` | retention: ledger/records window (0 = keep forever) |

## Private beta (Sprint 26, mocked swarm — see docs/beta.md for the runbook)

```powershell
python scripts/beta_swarm.py --workers 3 --units 12
# spins isolated workers, kills one mid-job, pauses/resumes another,
# asserts completion purely via APIs (homes kept in %TEMP%\beta-swarm-*)
```
# capacity: GET /network/capacity (cores/RAM/GPUs/versions/queue)
# support bundle: worker.exe --diagnostics (credential never printed)

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
