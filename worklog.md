# worklog.md — CreatorLab running journal (append-only)

> Log every sprint: date (UTC), sprint, goal, scope, changes, tests + outcome, decisions, next steps. Never rewrite history — append new entries.

---

## Template (copy for each sprint)

```markdown
## YYYY-MM-DD — Sprint N: <Title>
**Goal:** ...
**Scope (in / out):**
- In: ...
- Out: ...
**Exit condition (verbatim from roadmap):** ...
**Changes:**
- ...
**Tests run:**
- `...` → pass/fail (...)
**Decisions:**
- ...
**Next steps:**
- ...
```

---

## 2026-10-11 — Bootstrap: AGENTS.md + worklog.md + repo setup
**Goal:** Adopt sprint workflow (Plan → Scope → Implement → Verify → Commit+Push); create GitHub repo `CreatorLab` (public).
**Scope (in / out):**
- In: review docs; add AGENTS.md + worklog.md; `git init` + `gh repo create CreatorLab --public`; Sprint 0 plan.
- Out: any Sprint 0 implementation code (repo skeleton, coordinator/worker code) — that is Sprint 0 proper.
**Exit condition:** `gh repo view` shows `CreatorLab` public repo; `main` has initial commit with docs + AGENTS.md + worklog.md.
**Changes:**
- Added AGENTS.md (sprint workflow, tech stack, conventions), worklog.md (this file), .gitignore
- `git init -b main` + initial commit `f386130 docs(bootstrap): add AGENTS.md, worklog.md, docs baseline`
- `gh repo create CreatorLab --public` → https://github.com/jamesdileva/CreatorLab (PUBLIC), pushed `main`
**Tests run:**
- `git status` → clean, on `main` tracking `origin/main`
- `gh repo view --json name,description,visibility,url` → CreatorLab / PUBLIC / correct description — pass
**Decisions:**
- Repo name: `CreatorLab` (public). Description from architecture.md §1: "Community-powered distributed compute network that turns idle consumer PCs into a pool of AI/compute workers."
- Workflow per sprint: Plan → Scope → Implement → Verify (tests) → Commit+Push.
**Next steps:**
- Sprint 0: env baselines, LAN check, skeleton, .env.example, README, minimal coordinator+worker processes.

---

## 2026-10-11 — Sprint 0: Project Definition & Environment
**Goal:** Repository skeleton, dev environments, LAN reachability, hardware baselines, conventions (roadmap Sprint 0).
**Scope (in / out):**
- In (Full Sprint 0): skeleton dirs; README; .env.example; pyproject.toml; minimal coordinator `/health`; minimal worker ping (`--once`/`--loop`, persistent UUID); dashboard Vite stub; protocol/workload-spec/shared-types stubs; hello-compute stub; scripts/collect_baseline.py + check_lan.py; this-PC baseline; local + LAN verify; pytest suites.
- Out: Sprint 1+ work (SQLite/models/logging/error handling, registration endpoint, capability discovery, heartbeat loop, second-PC baseline — needs Iris Xe laptop).
**Exit condition (verbatim from roadmap):**
```text
PC A ──> Coordinator
PC B ──> Coordinator
```
Proven locally (PC A = this PC `james` 192.168.4.68 → localhost coordinator); PC B pending second machine running same worker command.
**Changes:**
- Root: README.md, .env.example, pyproject.toml (pytest pythonpath), .gitignore (+.worker_id)
- Coordinator: app/__init__.py, app/main.py (/health), requirements.txt, tests/test_health.py
- Worker: worker/__init__.py, worker/config.py (UUID, never hostname), worker/main.py (ping, --once/--loop), requirements.txt, tests/test_worker_id.py + test_ping.py
- Dashboard: package.json, vite.config.ts, tsconfig.json, index.html, src/main.tsx + App.tsx (Sprint 16 stub)
- Packages: protocol/__init__.py (PROTOCOL_VERSION) + README, workload-spec/README, shared-types/README
- workloads/hello-compute/README, tests/integration + end_to_end READMEs
- Scripts: collect_baseline.py (nvidia-smi → Win32_VideoController → Unknown), check_lan.py (resolve+TCP+/health)
- Baseline: docs/baseline-james.json (Windows 11, AMD 6c/12t 3.6GHz, 16GB RAM, AMD Radeon RX 6400 4GB, driver 32.0.21045.5002)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 5 passed
- Live: uvicorn coordinator :8000 + `worker/main.py --once` → ping OK `{'status':'ok',...}` — pass
- `scripts/check_lan.py --host 127.0.0.1 --port 8000` → resolve OK, tcp OK, GET /health 200 — pass
- `scripts/collect_baseline.py --out docs/baseline-james.json` → exit 0, GPU detected via Win32_VideoController — pass
- Dashboard: `npm install` (68 pkgs, 12s) + `npm run build` (tsc + vite, 1.18s) — pass
- Env: Python 3.14.3, Node v24.14.1, npm 11.11.0, SQLite 3.53.4, fastapi 0.139.0, sqlalchemy 2.0.51, psutil 7.2.2
**Decisions:**
- Python 3.14.3 satisfies "3.12+" requirement; no venv (global toolchain already has fastapi/uvicorn/sqlalchemy/pytest).
- Removed apps/*/tests/__init__.py (duplicate `tests` package collided on pythonpath); unique test module names instead.
- Fixed test httpx.Response mock (needs request=...), check_lan arrow `→`→`->` (cp1252 console), worker sys.path bootstrap for direct script run.
- `.worker_id` gitignored (per-machine identity); baseline JSON committed as Sprint 0 evidence.
- Dashboard stays stub until Sprint 16; protocol stays version-string-only until Phase 2.
**Next steps:**
- Sprint 1: coordinator skeleton (config, SQLite, SQLAlchemy worker table, logging, error handling, /health+DB check).
- Need Iris Xe laptop: run baseline script + worker `--coordinator-url http://192.168.4.68:8000 --once` for PC B exit proof.

---

## 2026-10-11 — Rename: GitHub repo CreatorLab → CommunityCompute
**Goal:** Align GitHub repo name with project/folder name `CommunityCompute` (local folder was always correct; `CreatorLab` was just the initial repo-name suggestion).
**Scope (in / out):**
- In: `gh repo rename CommunityCompute --yes`; `git remote set-url origin`; replace `CreatorLab`→`CommunityCompute` in AGENTS.md, README, .env.example, coordinator/worker strings, dashboard package + UI stub, protocol docstring; verify tests + push.
- Out: rewriting history entries below (append-only — old entries keep `CreatorLab` name as record).
**Changes:**
- `gh repo rename CommunityCompute --yes -R jamesdileva/CreatorLab` → https://github.com/jamesdileva/CommunityCompute (PUBLIC, same description)
- Renamed references in 12 files (incl. `creatorlab-dashboard` → `communitycompute-dashboard` in package.json + package-lock.json)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 5 passed
- `gh repo view jamesdileva/CommunityCompute --json name,description,visibility,url` → CommunityCompute / PUBLIC — pass
**Decisions:**
- Old URL `github.com/jamesdileva/CreatorLab` auto-redirects to the new name (GitHub keeps redirect on rename).
**Next steps:**
- Sprint 1: coordinator skeleton (done below).

---

## 2026-10-11 — Sprint 1: Coordinator Skeleton
**Goal:** Central control service; `GET /health` proves alive + SQLite-connected (roadmap Sprint 1).
**Scope (in / out):**
- In (Full Sprint 1): config (pydantic-settings), SQLite engine/session/Base, Worker table, basic logging, JSON error envelope, `/health` with `SELECT 1` + worker count; tests for each.
- Out: registration/heartbeat endpoints (S2/S4), capabilities (S3), jobs/work units (S5), auth/TLS, migrations (dev DB disposable), dashboard changes.
**Exit condition (verbatim from roadmap):** Opening `/health` proves the coordinator is alive and connected to SQLite.
**Changes:**
- New: app/config.py (COORDINATOR_HOST/PORT, DATABASE_URL default `sqlite:///./communitycompute.db`, LOG_LEVEL), app/db/__init__.py (engine with `check_same_thread=False`, SessionLocal, Base, init_db, get_db, check_database), app/models/worker.py (workers: UUID PK, version, hostname, status default `unknown`, first/last seen, updated_at), app/api/health.py (/health router, 503 on DB loss), app/main.py (lifespan init_db, logging, 404/422/500 JSON envelope), placeholder scheduler/services/schemas packages
- Rewrote: tests/test_health.py (tmp-DB dependency override; health+count+envelope tests); new tests/test_worker_model.py + test_config.py
- Touched: .env.example (+DATABASE_URL), README (DB note)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 11 passed
- Live uvicorn: `/health` → 200 `{'status':'ok','database':{'connected':True,'workers':0}}` — pass
- `GET /nope` → 404 `{'error':{'code':404,...}}` — pass
- Sprint-0 worker `--once` → ping OK (stable ID `a4228558…`, version string bumped) — pass
- `communitycompute.db` created on startup; `.tables` → `workers`; `SELECT count(*)` → 0 — pass
**Decisions:**
- Target package layout (api/scheduler/services/models/schemas/db) adopted now to avoid later churn; empty packages carry landing-note docstrings.
- `/health` depends on `get_db` so tests override with tmp DBs — no test pollution of dev DB.
- No Alembic: dev SQLite file is disposable (gitignored); migrations only when data worth keeping exists.
**Next steps:**
- Sprint 2: worker skeleton (config, persistent ID already done, registration endpoint + startup/shutdown) (done below).

---

## 2026-10-11 — Sprint 2: Worker Skeleton
**Goal:** Worker process connects to Coordinator; both PCs appear in `GET /workers` with unique Worker IDs (roadmap Sprint 2).
**Scope (in / out):**
- In (Full Sprint 2): registration endpoint `POST /workers/register` (idempotent upsert), `GET /workers`, `WorkerRegistration`/`WorkerOut` schemas, worker startup sequence + `--loop` re-register + graceful shutdown (SIGINT/SIGTERM/SIGBREAK), conftest.py shared tmp-DB fixture, tests.
- Out: heartbeat loop (S4), capabilities (S3), polling/execution (S6), auth (S20), dashboard.
**Exit condition (verbatim from roadmap):** Both computers appear in `GET /workers` with unique Worker IDs.
**Changes:**
- Coordinator: app/schemas/worker.py (WorkerRegistration: UUID id, version, optional hostname; WorkerOut), app/api/workers.py (register upsert → status `online` + last_seen; list ordered by first_seen), main.py mounts router, version → 0.1.0-sprint2, tests/conftest.py (shared client fixture), tests/test_workers.py (5 tests: create, idempotent re-register, two unique IDs, bad-UUID 422, missing version 422), test_health.py refactored onto conftest
- Worker: worker/__init__.py `__version__`, worker/registration.py (payload + POST client), worker/main.py rewritten (startup sequence, `--once` register, `--loop` re-register with retry, threading stop-event, signal handlers SIGINT/SIGTERM/SIGBREAK); `.gitignore` now ignores `.worker_id*`
- README: status + Sprint 2 quickstart
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 22 passed
- `python -m pytest apps/coordinator/tests apps/worker/tests` (random order) → 22 passed
- Live: Worker A (`--once`) + Worker B (`--once --worker-id-file .worker_id_b`) → both `status=online`; `GET /workers` → 2 unique IDs — pass
- `--loop` worker + CTRL_BREAK → `signal 21 - shutting down` → `stopped` → exit 0 — pass
- cp1252 console fix: replaced `→`/`—` in worker *console output* (docstrings keep Unicode) — pass
**Decisions:**
- `POST /workers/register` is an idempotent upsert (same ID refreshes version/hostname/last_seen); registration response returns the full WorkerOut row.
- Windows signal reality check: `CTRL_C_EVENT` via `os.kill` did NOT deliver to handler (possibly detached from console); `CTRL_BREAK_EVENT` → SIGBREAK (21) works and is now registered alongside SIGINT/SIGTERM. Turtle: `Ctrl+C` in an attached console still delivers SIGINT.
- `.worker_id*` gitignored so per-machine ID files never commit; second PC keeps own file locally.
**Next steps:**
- Sprint 3: hardware capability discovery (CPU/RAM/OS/GPU/VRAM/driver, capability schema + persistence) — needs worker-side discovery + coordinator endpoint/table (done below).

---

## 2026-10-11 — Sprint 3: Hardware Capability Discovery
**Goal:** Workers auto-discover CPU/RAM/OS/GPU/VRAM/driver; API shows different profiles per machine. No manual hardware entry allowed (roadmap Sprint 3).
**Scope (in / out):**
- In (Full Sprint 3): GPU provider adapters (nvidia-smi → Win32 WMI → Unknown fallback), CPU/RAM/OS discovery, versioned capability schema, `worker_capabilities` table, `POST /workers/{id}/capabilities` + `GET /workers/{id}` + capabilities in `GET /workers`, worker reports capabilities after registration (`--no-capabilities` to skip), collect_baseline.py refactored to thin wrapper over shared discovery, tests.
- Out: live utilization/temperature telemetry (S12), capability benchmarking (guide §7), workload requirements matching (S9), heartbeat loop (S4).
**Exit condition (verbatim from roadmap):** Dashboard/API shows different capability profiles for the two machines. No manual hardware entry is allowed.
**Changes:**
- Worker: worker/capabilities/{schema,cpu,ram,os_info,discover,client}.py + gpu/{base,nvidia,wmi,unknown,registry}.py; main.py reports profile after registration; requirements.txt +pydantic
- Coordinator: app/models/capability.py (worker_capabilities: worker_id PK FK, JSON profile, updated_at), app/schemas/capability.py (extra="forbid" — reject junk), app/api/workers.py (+POST capabilities upsert, +GET /workers/{id}, list embeds capabilities), schemas/worker.py (+capabilities field)
- scripts/collect_baseline.py: now wraps discover_capabilities() (single source of truth); docs/baseline-james.json regenerated (schema_version added, freq_mhz float)
- README: status + quickstart
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 44 passed
- `python -m pytest apps/coordinator/tests apps/worker/tests` (random order) → 44 passed
- Live: worker `--once` → `capabilities reported: amd AMD Radeon RX 6400 4080MB`; `GET /workers` → cpu 12/6 cores, 16258MB RAM, single RX 6400 4080MB entry — pass
- `collect_baseline.py` regenerated baseline matches live-reported values (parity) — pass
**Decisions:**
- Registry runs real providers, appends UnknownProvider only when nothing detected (first live run wrongly double-listed "undetected" — fixed).
- Coordinator defines its own receive schema with `extra="forbid"` → malformed/typo'd profiles rejected 422 (fail closed at the API boundary).
- capabilities attached to Worker transiently for serialization; no ORM relationship yet (fine for prototype).
- Schema duplicated worker-side/coordinator-side for now; moving to packages/protocol as shared contract when more message types land (Sprint 5 Job/WorkUnit).
**Next steps:**
- Sprint 4: heartbeats & availability (endpoint, loop, last-seen → online/offline, basic utilization reporting) (done below).

---

## 2026-10-11 — Sprint 4: Heartbeats & Availability
**Goal:** Know whether workers are alive and available; silence means offline (roadmap Sprint 4).
**Scope (in / out):**
- In (Full Sprint 4): heartbeat endpoint + log table, worker heartbeat loop (psutil CPU/RAM + nvidia-smi GPU util), last-seen → online/offline derivation with configurable timeout, utilization on worker rows, tests incl. failure transition test.
- Out: availability policy engine (S11), temp monitoring (S12), WebSocket control (S17), dashboard.
**Exit condition (verbatim from roadmap):** Stopping a Worker causes the Coordinator to eventually mark it offline. Restarting it returns it to online status.
**Changes:**
- Coordinator: schemas/heartbeat.py (Heartbeat + ResourceSnapshot, extra=forbid), models/heartbeat.py (append-only worker_heartbeats), models/worker.py (+cpu/gpu/ram columns), config (+HEARTBEAT_TIMEOUT_SECONDS=60), services/availability.py (effective_status), api/heartbeats.py (POST heartbeat upsert+log, GET heartbeats log), api/workers.py (derived status in list/detail), db/__init__.py additive ALTER-column bootstrapping for existing dev DBs, version → 0.1.0-sprint4
- Worker: worker/heartbeat.py (payload + client), main.py `--loop` restructured: register once (with capabilities) → heartbeat every interval
- .env.example, README
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 54 passed
- Live (timeout=8s, interval=3s): while running → `online` cpu 36.1% ram 6359MB; kill → +10s → `offline`; restart → `online`; heartbeat log accumulates — pass
**Decisions:**
- Status is *derived*, never trusted from the worker: online iff last_seen within timeout; explicit states (paused/disabled) reserved for Sprint 11.
- Additive-column bootstrap (`_apply_additive_columns`) instead of Alembic for now — dev DBs survive additive sprints; real migrations when data matters.
- Heartbeat log append-only (audit/diagnostics + Sprint 27 accounting precursor); latest snapshot denormalized onto workers for cheap reads.
- `--loop` now registers once then heartbeats (previously re-registered each interval) — registration idempotency retained via `--once`.
**Next steps:**
- Sprint 5: job + work-unit models, job submission, work-unit generation, state machine, job status endpoint (M1 groundwork) (done below).

---

## 2026-10-11 — Sprint 5: Job Model
**Goal:** Jobs and Work Units exist; deterministic decomposition on submit (roadmap Sprint 5).
**Scope (in / out):**
- In (Full Sprint 5): Job + WorkUnit models, transactional create (job + units together), deterministic range generation with last-chunk clamp, state-machine transition rules, POST/GET /jobs, GET /jobs/{id} with per-status counts, tests.
- Out: scheduler assignment/leasing execution (S6/S7), workload requirement matching (S9), aggregation of results (S6), retries driven by scheduler (transitions validated only).
**Exit condition (verbatim from roadmap):** Submitting 1,000 units, chunk size 100, creates exactly 10 Work Units with correct ranges/identifiers.
**Changes:**
- Coordinator: models/job.py + models/work_unit.py (unique (job_id, sequence)), schemas/job.py (JobCreate positive-only validation; JobOut; JobStatusOut with counts+units), services/jobs.py (plan_units, unit_count, create_job atomic, job_status aggregates), services/state.py (unit + job transition matrices), api/jobs.py (POST/GET /jobs, GET /jobs/{id}), version → 0.1.0-sprint5
- tests: test_unit_generation.py (5), test_state_machine.py (4), test_jobs.py (6)
- README quickstart
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 69 passed
- Live: POST /jobs {1000/100} → job queued; GET /jobs/{id} → 10 units, counts {queued:10}, first (1,1,100), last (10,901,1000), 10 unique IDs — pass
**Decisions:**
- Ranges are deterministic (1-based inclusive, ceil-div chunking) so Sprint 6 verification is exact — coordinator will know expected results for hello-compute.
- Job params copied at creation (immutability enforced in service + test); job row never mutated post-create.
- State machine encodes transition rules now; nothing *drives* transitions until Sprint 6/7 (validated-only).
- Job status aggregates read from unit statuses (no background rollup job) — simple and correct for prototype.
**Next steps:**
- Sprint 6: first distributed workload — worker polling + assignment + execution + result upload + aggregation (M1) (done below).

---

## 2026-10-11 — Sprint 6: First Distributed Workload (M1)
**Goal:** One submitted Job divided across workers; verified results; correct aggregate (roadmap Sprint 6, milestone M1).
**Scope (in / out):**
- In (Full Sprint 6): protocol package (version + fail-closed check), hello-compute reference (coordinator) + executor (worker, validates before executing), FIFO claim, result verification + persistence, job aggregation + rollup status, worker work loop.
- Out: leases/expiry + retries (S7), requirement/capability matching (S9), WebSocket (S17), adapter registry formalization (S13).
**Exit condition (verbatim from roadmap):** One submitted Job is divided across both PCs and produces one correct final result. (This is the first major project milestone.)
**Changes:**
- packages/protocol: PROTOCOL_VERSION + message names + `version_supported()`; path bootstrap added to both apps (`app/__init__.py`, worker `main.py`)
- Coordinator: services/workloads/hello_compute.py (sum/hash + output_hash), models/result.py, work_units +assigned_worker_id/dispatched_at (additive migration), services/work.py (claim, submit+verify, aggregate, rollup), api/work.py (GET /work/{worker}, POST /work/{unit}/result, 422 on mismatch), schemas/work.py, JobStatusOut +aggregate/assigned_worker_id, version → 0.1.0-sprint6
- Worker: worker/execution/hello_compute.py (executor + registry + validation), worker/work.py (claim/submit clients), main.py work cycle in loop (`--no-work` skip)
- tests: coordinator test_work.py (11), worker test_executor.py + test_work_client.py (11)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 91 passed
- `python -m pytest apps/coordinator/tests apps/worker/tests` (random order) → 91 passed
- Live M1 (two workers, separate ID files, interval 2s): job 20×1 → status **completed**, counts {completed:20}, aggregate **final=210** (=Σ1..20); split 10 units A / 10 units B — pass
- Corrupted direct POST (value 999999) → 422 rejected, unit failed — pass
**Decisions:**
- Verification at the coordinator: it recomputes expected values from deterministic ranges — never trusts worker output (architecture §18).
- Worker fails closed: protocol version, workload type, range sanity all validated before execution; executor registry rejects unknown workloads.
- Claim is FIFO with optimistic dispatch (no lease yet); duplicate verified results are idempotent 200; mismatches fail the unit (job → failed).
- Error envelope nests `detail` under `error.message` (existing handler); adjusted tests accordingly.
**Next steps:**
- Sprint 7: leasing (lease_id/expires_at/attempt_number), reclaim expired work, kill-worker retry test (M2 fault tolerance) (done below).

---

## 2026-10-11 — Sprint 7: Work Unit Leasing (M2)
**Goal:** Worker failure is survivable — expired leases return to the queue (roadmap Sprint 7, milestone M2).
**Scope (in / out):**
- In (Full Sprint 7): lease columns on work_units, work_unit_attempts table, lazy sweep-on-claim, lease-issue on claim, attempt outcomes (completed/failed/expired), duplicate resubmission 200 vs late-result 409, worker POST claim + 409 tolerance + --execution-delay, quick-reference.md.
- Out: retry policy tuning/backoff, redundant execution (S23), scheduler scoring (S31).
**Exit condition (verbatim from roadmap):** Start a Job, kill one Worker during execution, and confirm its unfinished Work Units are eventually completed by the other Worker.
**Changes:**
- Coordinator: models/work_unit.py (+lease_id/lease_worker_id/started_at/expires_at/attempt_number), models/attempt.py, config +LEASE_DURATION_SECONDS=60, services/work.py (claim issues lease + attempt row; _sweep_expired_leases on every claim; submit closes attempts, clears leases, raises Conflict on late results), api/work.py (POST claim; 409 mapping), db additive migration (version stays 0.1.0-sprint6 — no protocol shape change this sprint)
- Worker: work.py claim→POST + 409→already_completed, main.py --execution-delay knob
- tests: test_leasing.py (6), test_work.py claims→POST, worker 409 test
- NEW docs: quick-reference.md (two-PC setup, commands, env table, troubleshooting)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 98 passed
- `python -m pytest apps/coordinator/tests apps/worker/tests` (random order) → 98 passed
- Live M2 (lease 4s): A --execution-delay 8s + B normal, job 4x1; kill A mid-run -> B completes all: status **completed**, aggregate **final=10**; DB shows unit attempt 1 (A) `expired` -> attempt 2 (B) `completed` — pass
**Decisions:**
- Lazy sweep on claim instead of a background reaper (prototype: no timers/threads on the coordinator; sweep cost is one indexed query).
- Attempt history is forever (audit + Sprint 27 accounting); lease visibility is the `work_units` columns (hot path).
- 409 only on *conflicting* late results; identical resubmits stay 200 idempotent (worker 409-tolerant logs + moves on).
- `--execution-delay` is a failure-test knob only (implementation-guide §16 deliberate failure tests), not production behavior.
**Next steps:**
- Sprint 8: classified verification + duplicate execution (done below).
- Two-machine E2E still pending (see quick-reference.md).
- Two-machine E2E still pending (laptop on LAN, `python apps/worker/worker/main.py --coordinator-url http://192.168.4.68:8000 --loop`).

---

## 2026-10-11 — Sprint 8: Result Verification
**Goal:** Correct results accepted, corrupted rejected — with classified reasons and optional duplicate agreement (roadmap Sprint 8).
**Scope (in / out):**
- In (Full Sprint 8): failure_kind on results (5 kinds) in 422 detail, verify_sample on jobs, duplicate check units claimed by a *different* worker, match → verified_by / mismatch → both failed (overturn), completed→failed matrix transition, rejections in aggregate, tests.
- Out: reputation scoring (S23), challenge workload types beyond hello-compute (later), worker-side changes (verification is coordinator-side).
**Exit condition (verbatim from roadmap):** A deliberately corrupted result is rejected. A correct result is accepted.
**Changes:**
- Coordinator: models/result.py (+failure_kind, verified_by), models/work_unit.py (+verify_of; dropped (job,seq) unique — duplicates share sequences), models/job.py (+verify_sample), schemas (JobCreate/JobOut verify_sample, ResultOut +fields), services/work.py (_classify, _sampled, _maybe_spawn_duplicate, _confirm_original/_overturn_original; aggregate from originals only + rejections), services/state.py (completed→failed overturn), 422 detail +failure_kind, version → 0.1.0-sprint8
- tests: test_verification.py (10), test_state_machine.py overturn case
- quick-reference.md (verify_sample snippet, failure kinds, constraint-reset note)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 109 passed
- Live: sample=1.0 job 2x1 → 4 units completed, aggregate final=3 (no double-count), originals carry verified_by — pass
- Live disagreement: duplicate value 7 vs confirmed 1 → 422 verification_disagreement, both units failed, job failed — pass
- Live kinds: corrupt value → value_mismatch, unknown op → unsupported_workload — pass
**Decisions:**
- Duplicates are judged on *reproduction* of the confirmed original, not re-derivation — caught a design bug mid-sprint (expectation-first made disagreement unreachable).
- verified_by naming the confirmer gives Sprint 23 reputation a free data source later.
- Dropped unique constraint needs a dev-DB reset (documented in quick-reference); creation code still guarantees one original per sequence.
- No worker changes: the executor's deterministic math already matched; verification lives server-side by design.
**Next steps:**
- Sprint 13: workload adapter system (registry + lifecycle) — prepare for real AI workloads (done below).
- Two-machine E2E still pending (see quick-reference.md).

---

## 2026-10-11 — Sprint 9: Scheduler Compatibility
**Goal:** Stop treating every machine as identical — route only compatible work (roadmap Sprint 9).
**Scope (in / out):**
- In (Full Sprint 9): declarative Requirements schema on jobs, worker profile lookup at claim time, compat filter in claim path, runtimes in capabilities, routing tests.
- Out: H1/H2/H3 tiers + explanation endpoint (S10), scoring (S31), policy-aware routing (S11), runtime capability *probes* (benchmarks — guide §9).
**Exit condition (verbatim from roadmap):** Create two Work Unit types (CPU-only, GPU-required). The scheduler sends each only to compatible Workers.
**Changes:**
- Coordinator: schemas/job.py (Requirements extra="forbid" — typo'd keys rejected 422; JobCreate.requirements; JobOut/JobStatusOut echo), models/job.py (+requirements JSON), services/compat.py (check() in architecture §10 order: CPU → RAM → OS → runtime → GPU vendor/VRAM), services/jobs.py (requirements stored), services/work.py (claim filters candidates by worker's stored profile; same-worker duplicate skip kept), api/jobs.py (status echoes verify_sample/requirements), version → 0.1.0-sprint9
- Worker: capabilities schema +discover +runtimes (executor registry), worker/__init__.py path bootstrap (robust standalone `packages.protocol` import)
- tests: test_compat.py (16), test_claim_routing.py (8), test_discover runtimes
- quick-reference.md requirements snippets
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 129 passed
- random order → 129 passed
- Live: both workers report runtimes ['hello_compute']; CPU-only job (4 units) → **completed** final=10 across both workers; amd-GPU job (2) → **completed** final=3; nvidia-GPU job → stays **queued** (correctly starves both workers) — pass
**Decisions:**
- Conventions: empty requirements = runs anywhere (legacy workers, unrestricted jobs); non-empty requirements with no reported profile = incompatible (fail closed).
- Two bugs caught by tests before commit: (1) default-populated requirements dict was truthy-but-vacuous → `exclude_unset` when persisting; (2) compat treated vacuous dicts as real requirements → normalize None/False before matching.
- Filtering happens per-candidate at claim time, O(queue) — fine for prototype; Sprint 31 scoring will want precomputed match sets.
- `gpu: false` is not a "CPU-only" flag in the matching sense — it simply doesn't constrain; CPU-only jobs are expressed with `cpu_cores`/`ram_mb`.
**Next steps:**
- Sprint 10: hardware tiers + capability explanation (scheduler says why).
- Two-machine E2E still pending (see quick-reference.md).
## 2026-10-11 — Sprint 10: Hardware Tiers
**Goal:** Formalize capability classes; scheduler explains compatibility (roadmap Sprint 10, milestone M3).
**Scope (in / out):**
- In (Full Sprint 10): per-axis H1/H2/H3 tiers (GPU/CPU/RAM), tiers on worker detail, `GET /jobs/{id}/compatibility/{wid}` explanation endpoint with per-dimension rows, score stubs exported for Sprint 31 (not wired).
- Out: score-driven scheduling (S31), benchmarked tiers (guide §9), policy-aware routing (S11), dashboard visualization (S16).
**Exit condition (verbatim from roadmap):** The two prototype machines receive different hardware capability profiles and the scheduler can explain why a Work Unit is or is not compatible.
**Changes:**
- Coordinator: services/tiers.py (gpu_tier/cpu_tier/ram_tier + hardware_tiers; VRAM bands 4/12GB, core bands 4/8, RAM bands 8/32GB; integrated/undetected → H1; best GPU wins), services/explain.py (per-check rows: dimension/need/have/passed/reason), api/jobs.py (compatibility endpoint), api/workers.py (tiers in _to_out), schemas/worker.py (+tiers)
- tests: test_tiers.py (9), test_explain.py (8)
- quick-reference.md (tiers + explanation endpoints)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 147 passed
- random order → 147 passed
- Live: worker detail tiers `{'gpu': 'H1', 'cpu': 'H2', 'ram': 'H2'}` (RX 6400 4GB/6c/16GB); amd-GPU job → compatible, gpu row passed; nvidia-24GB job → incompatible, precise reason row — pass
**Decisions:**
- Boundary convention: `<= floor` → H1 (a 4GB GPU is H1, 12GB is H2) — band label covers the lower bound inclusively; tests + quick-reference document the bands.
- `gpu: None` distinguishes "has no GPU" from cpu/ram's `unknown` (no data); API surfaces H1/H2/H3/unknown.
- Score functions exported but unused: Sprint 31 wiring must come after compatibility correctness is proven (roadmap: no scoring until proven).
**Next steps:**
- Sprint 11: contributor policy engine (idle-only, CPU/GPU %, temperature ceiling, battery, schedule, pause).
- Two-machine E2E still pending (see quick-reference.md).

---

## 2026-10-11 — Sprint 11: Contributor Policy Engine
**Goal:** Contributor controls when the machine contributes; conditions trip → stops accepting work (roadmap Sprint 11).
**Scope (in / out):**
- In (Full Sprint 11): AvailabilityPolicy schema, machine-state sampler (psutil/nvidia-smi/battery/idle), ordered engine with reasons, persisted policy.json, --pause/--resume/--policy-file CLI, heartbeat availability → coordinator "paused" status, tests.
- Out: execution-limit enforcement (separate control per guide §18, later), fullscreen/process detection (guide §17 says don't), dashboard controls (S16), GPU temp on non-NVIDIA (undetectable → skips? no: ceiling + unknown temp denies).
**Exit condition (verbatim from roadmap):** When a configured condition occurs, the Worker stops accepting new work. Pressing Pause immediately prevents additional work from being assigned.
**Changes:**
- Worker: worker/policy/{schema,state,engine,store}.py; main.py gates work cycle on policy (denied → no claim), heartbeat carries `available`, pause/resume CLI (exit code 0 before networking)
- Coordinator: Heartbeat.available (extra field, backwards compatible); heartbeat sets status online|paused; availability service treats `paused` as explicit
- tests: test_policy_engine.py (19), test_policy_store.py (6), test_policy_wiring.py (5), heartbeat availability cases (4)
- .gitignore +policy.json (per-machine, never committed)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 178 passed
- random order → 178 passed
- Live: heartbeat available=false → worker `paused`; available=true → `online`; missing field → derived online — pass
- Live gate: worker with paused policy prints "holding off work: paused by contributor" and claims nothing (unit test + manual) — pass
**Decisions:**
- Fail closed on unknown signals: idle-only + undetectable idle denies; temperature ceiling + undetectable temp denies (never blind-run hot).
- Midnight-wrap schedule windows handled explicitly (bug caught by test: wrap branch let every hour through).
- Heartbeat is backwards compatible: workers without `available` keep liveness-derived status; pause is explicit-only.
- Worker gating is the primary control (coordinator `paused` is informational, not an enforcement point) — worker never claims while denied.
**Next steps:**
- Sprint 12: resource monitoring (temperature/telemetry richness, availability transitions).
- Two-machine E2E still pending (see quick-reference.md).

---

## 2026-10-11 — Sprint 12: Resource Monitoring
**Goal:** Continuous local awareness; high-load auto-transitions available → throttled (roadmap Sprint 12).
**Scope (in / out):**
- In (Full Sprint 12): worker_resource_samples table + endpoints, one-sample-per-tick pipeline (telemetry + gate + heartbeat), availability object with reason, throttled status, policy re-read per tick, gpu_stats single-call helper.
- Out: execution-limit enforcement (guide §18 separate control, later), dashboard (S16), process enumeration (guide §17: measurable signals only), history retention policy.
**Exit condition (verbatim from roadmap):** Run a high-load application and observe the Worker automatically transition from available to unavailable/throttled according to policy.
**Changes:**
- Coordinator: models/sample.py (worker_resource_samples), schemas/sample.py, api/resources.py (POST/GET /workers/{id}/resources), Heartbeat.availability {available,paused,reason} replaces the bare bool, heartbeat → status online|throttled|paused, availability._EXPLICIT += throttled
- Worker: worker/gpu_stats.py (single nvidia-smi query), monitoring.py (build_report/report_resources), state sampler uses shared helper, main loop: policy reload per tick + one sample per tick + `--heartbeat-interval`
- tests: test_resources.py (8), test_monitoring.py (6), wiring tests restructured for the new cadence
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 196 passed
- random order → 196 passed
- Live: policy {max_cpu_percent: 0} → status **throttled**, log "holding off work: cpu X% > limit 0.0%", job stayed queued (0 claims); policy {} → **online**, job completed (2/2); 8 telemetry samples accumulated — pass
**Decisions:**
- Policy file re-read each tick (cheap JSON read; corrupt → defaults) so contributor edits apply within one tick — live check caught startup-only loading first.
- Status vocabulary: online | throttled (policy denies) | paused (explicit) | offline (heartbeat timeout); throttled is explicit so it isn't mis-derived.
- One nvidia-smi call + one CPU sample per tick shared by telemetry/policy/heartbeat (previously two).
- Telemetry POST failures are swallowed (None return) — monitoring must never break the work loop.
**Next steps:**
- Sprint 13: workload adapter system (registry + lifecycle) — prepare for real AI workloads.
- Two-machine E2E still pending (see quick-reference.md).

---

## 2026-10-11 — Sprint 13: Workload Adapter System
**Goal:** Scheduler separated from workload implementation (roadmap Sprint 13).
**Scope (in / out):**
- In (Full Sprint 13): WorkloadExecutor interface (metadata, can_execute, prepare/execute/verify/cleanup), worker registry + run_unit lifecycle runner, hello-compute refactored onto the interface, second workload stats_range (both sides), coordinator verification dispatch via workload registry.
- Out: embeddings/image executors (S14), model cache (S15), sandboxing (S22).
**Exit condition (verbatim from roadmap):** Two different workload implementations run through the same scheduler without scheduler-specific branching.
**Changes:**
- Worker: worker/execution/executor.py (interface + lifecycle runner + ExecutorMetadata), registry.py (executor_for/list_executors/supported_runtimes/run_unit), hello_compute.py (interface impl; public compute/output_hash unchanged), stats_range.py (new workload, dict payload, own verify), main.py run_unit wiring, capabilities discover → runtimes from registry
- Coordinator: services/workloads/__init__.py (expected()/output_hash() dispatch), services/workloads/stats_range.py (reference), services/work.py (_classify dispatches by workload_type)
- tests: test_executor.py (rewritten: 16), test_workload_registry.py (6)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 207 passed
- random order → 207 passed
- Live: worker advertises runtimes [hello_compute, stats_range]; both job types claimed+executed+**verified** through the same endpoint (values 1, 2 scalar and {'count':1,...} dicts); both jobs draining (snapshot at +12s: 2/4 and 2/3, zero failures) — pass
**Decisions:**
- Lifecycle order **prepare → validate → execute → verify → cleanup** (verify before cleanup: verifier may need scratch state) — first draft had cleanup in finally-before-verify; test caught it.
- Stage failures map to failed UnitResults with distinct prefixes (prepare failed / rejected / execution error / verify crashed) → sprint-8 failure kinds stay precise.
- Executor metadata declares requirements (cpu_cores, gpu...) enforced in can_execute against optional capabilities; scheduler-side compat (S9) remains the routing authority.
- Second workload needed new coordinator reference math (stats_range); unknown types already flow to unsupported_workload (422) unchanged.
**Next steps:**
- Sprint 16: dashboard (contributor + network views over the APIs built so far) (done below).
- Two-machine E2E still pending (see quick-reference.md).

---

## 2026-10-11 — Sprint 16: Dashboard
**Goal:** Both PCs' activity understandable without logs — contributor + network views (roadmap Sprint 16).
**Scope (in / out):**
- In (Full Sprint 16): React+TS dashboard (typed API client, contributor tab, network tab), coordinator endpoints (pause/resume, network summary, current work, contribution stats), operator-pause enforcement in claim path.
- Out: auth-gated views, WebSocket live updates (S17), historical charts.
**Exit condition (verbatim from roadmap):** A user can visually understand what both PCs are doing without inspecting logs.
**Changes:**
- Coordinator: models/worker.py (+paused_by_operator), services/availability.py (operator pause wins), api/workers.py (POST /workers/{id}/pause|resume), api/network.py (GET /network/summary, /workers/{id}/work, /workers/{id}/stats), services/work.py (claim refuses operator-paused workers), db additive migration, version → 0.1.0-sprint16
- Dashboard: src/types.ts, src/services/api.ts, src/components/{ContributorView,NetworkView}.tsx, App.tsx (tabs + 5s refresh), vite proxy expanded, package version
- tests: test_network.py (8)
- quick-reference.md (dashboard section; removed a duplicated snippet + orphan from earlier bad edits)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 250 passed
- `npm run build` (tsc --noEmit + vite) → pass
- Live (single call): dashboard `/` → 200; proxy /workers /network/summary /jobs → 200; job 8 units drained to 2/4; **UI pause → claims frozen (still 2/4)**; resume → completed 4/4; stats 4 completed / 0.133s; network summary via proxy reports completed 4 / 5m — pass
**Decisions:**
- Operator pause (dashboard) is *enforcement*: claims return `{}` and availability treats `paused_by_operator` as explicitly-paused. It is distinct from worker self-pause (availability.paused) and policy throttling — three different pause meanings, all visible as one status.
- Dashboard refresh = 5s polling (no new deps); WebSocket updates are Sprint 17, not now.
- Fixed quick-reference debt found while editing: a duplicated workload snippet + an orphan comment line from prior misplaced edits; confirmed file coherent after repair.
**Next steps:**
- Sprint 17: WebSocket control plane (live notifications, pause/cancel messages, no aggressive polling).
- Two-machine E2E still pending (see quick-reference.md).

---

## 2026-10-11 — Sprint 15: Model Cache
**Goal:** Fetch once, reuse forever; workers advertise cached models; scheduler prefers cache-warm workers (roadmap Sprint 15).
**Scope (in / out):**
- In (Full Sprint 15): ModelManifest + ModelCache (ensure/verify/prune/evict), executor prepare() fetch + cache_hit metrics, cached_models in capabilities (+ re-report on change), claim body cached_models + cache-first ordering, requirements.model validated, result metrics persisted.
- Out: real multi-MB/GB weight files (machinery proven on tiny bundles; same paths), remote download auth/resume, per-policy cache quotas.
**Exit condition (verbatim from roadmap):** The first Work Unit downloads a model. Subsequent Work Units reuse the local model without downloading it again.
**Changes:**
- Worker: worker/models/{manifest,cache}.py (inline/file/http sources, sha256 verify, LRU prune, offline reuse), execution/embeddings executor prepare() + metrics {cache_hit, model}, capabilities cached_models + discovery, main.py re-reports capabilities on change + claim sends cached names + --model-cache-dir, MODEL_CACHE_DIR/worker/.gitignore models? no — models/ is per-machine runtime data (add to .gitignore)
- Coordinator: Requirements.model, ClaimRequest.cached_models, claim ordering cache-first (stable FIFO groups), Result.metrics persisted + exposed
- tests: test_model_cache.py (10), test_model_prepare.py (5), test_model_preference.py (3)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 243 passed
- random order → 243 passed
- Live: model-required embeddings job → unit metrics cache_hit 0,1,1 (fetch then reuse); GET /workers shows cached_models [hashing-embedder@1]; models/ dir holds artifact + marker; second job → zero fetches — pass
**Decisions:**
- Machinery-over-megabytes: 19-byte inline bundle exercises fetch/verify/reuse/report/prefer/prune identically to GB weights (stated in code + here).
- `model` is preference, NOT a compat gate — check() excludes it, else workers could never reach the first fetch that warms the cache (caught by test before commit).
- prepare() owns fetching (lifecycle stage, fails the unit loudly on CacheError); UnitResult.metrics merged into submit body so cache evidence rides the existing Result path.
- LRU needs real fetch timestamps recorded in the marker file (mtime alone is same-second-ambiguous); `now or time.time()` → `now if not None` bug class caught by prune test.
**Next steps:**
- Sprint 16: dashboard (contributor + network views over the APIs built so far).
- Two-machine E2E still pending (see quick-reference.md).

---

## 2026-10-11 — Sprint 14: First Real AI Workload (M4)
**Goal:** A real AI workload — embeddings — divided into batches, processed by compatible machines, verified by re-derivation (roadmap Sprint 14, milestone M4).
**Scope (in / out):**
- In (Full Sprint 14): Embedder adapter interface + HashingEmbedder, EmbeddingsExecutor, deterministic synthetic corpus, coordinator reference math + registry dispatch, metrics in results, tests.
- Out: model-backed embedders (need model cache, Sprint 15), real corpus fetch (Sprint 15), batch-size autotuning, embedding aggregation (counts only for AI jobs).
**Exit condition (verbatim from roadmap):** A real AI Job is divided into multiple Work Units and processed by the available compatible machines.
**Changes:**
- Worker: worker/execution/embeddings/{embedder,executor}.py (Embedder protocol, HashingEmbedder L2-normalized dim-configurable, deterministic corpus_text, executor batch + local verify), registry +1 workload, UnitResult.metrics, main.py forwards executor metrics
- Coordinator: services/workloads/embeddings.py (identical reference math), __init__.py expected()/output_hash() take params (dim), work.py passes job params
- tests: worker test_embeddings_executor.py (11: determinism, normalization, tamper catch, cross-side parity via importlib), coordinator test_embeddings.py (3: verified batch, tamper rejected, two-worker split), registry dispatch tests
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 224 passed
- random order → 224 passed
- Live M4: embeddings job (40 docs, 4x10 batches, dim 64) → **completed** 4/4 verified; per-unit execution_ms 0.7-0.9ms recorded — pass
**Decisions:**
- Hashing (feature-hash) embedder chosen over a downloaded model: zero-download prototype, deterministic (verification exact), and the Embedder interface means a sentence-transformers/ONNX backend slots in without scheduler changes (documented in code + quick-reference).
- Corpus is synthetic/deterministic (documented everywhere); coordinator re-derives vectors, so tampering is caught exactly like hello-compute mismatches.
- Duplicate file-basename lesson: two `test_embeddings.py` collide under pytest's rootdir collection (no test __init__ packages) → worker file renamed `test_embeddings_executor.py`.
- Executor-provided `metrics` (docs, dim) merged into result metrics so performance data rides the existing Result path.
**Next steps:**
- Sprint 15: model cache (manifests, versions, reuse, scheduler preference for cached workers).
- Two-machine E2E still pending (see quick-reference.md).

---

## 2026-10-13 — Sprint 17: WebSocket Control Plane
**Goal:** A newly-available worker receives a work notification without aggressive polling (roadmap Sprint 17).
**Scope (in / out):**
- In (Full Sprint 17): `WS /ws/worker/{id}` (hello + heartbeat-over-socket reusing the HTTP handler), connection registry with thread-safe fan-out, `work_available` broadcast on job submit, pause/resume frames on operator action, worker `ws_client` (background thread, wake-event, capped-backoff reconnect, `--no-ws`), HTTP fallback when the socket is down, tests + live proof.
- Out: WebSocket dashboard updates (dashboard keeps 5s polling), WS auth (S20), cancel messages (no cancel endpoint exists yet), per-job downstream fan-out beyond submit broadcast.
**Exit condition (verbatim from roadmap):** A newly available Worker receives a work notification without requiring aggressive polling.
**Changes:**
- Coordinator: app/api/ws.py (hello → hello_ack + liveness touch; heartbeat → shared `apply_heartbeat` with HTTP POST, refactored out of `receive_heartbeat`; unknown worker → 4404 close), app/services/ws_registry.py (worker_id → socket+loop, `send`/`send_from_thread`/`broadcast_from_thread`), api/jobs.py (submit broadcasts `work_available`), api/workers.py (pause/resume push frames), main.py mounts router, requirements.txt +websockets, version → 0.1.0-sprint17
- Worker: worker/ws_client.py (URL builder, hello/heartbeat message builders, `dispatch_message` wake-on-`work_available`, `next_backoff` 1s→8s cap, `ws_loop` thread: hello → recv/dispatch → socket heartbeats → reconnect), main.py (`--no-ws`, wake/ws_connected events, `_wait_for_next_tick` single wake-based wait per tick, HTTP heartbeat skipped while socket owns cadence, signal handler breaks the sleep)
- tests: coordinator test_ws.py (8: hello_ack, heartbeat reuse + last_seen, bad-shape/type errors, 4404 refusal, pause/resume + submit wiring via monkeypatch, registry send/unregister), worker test_ws_client.py (17: URL/message shapes, dispatch incl. wake, backoff cap, wait helper, hello-rejection reconnect regression, HTTP-skip-while-connected wiring)
- quick-reference.md (control-socket section), README status
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 275 passed
- random order → 275 passed
- Live (fresh DB, worker `--interval 30 --heartbeat-interval 5`): 1-unit job → **completed in 2.1s** (notification, not polling); coordinator logged socket heartbeats while worker sent zero over HTTP (exactly one channel); operator pause frame arrived over WS; kill → restart → reconnect → second job completed — pass
**Decisions:**
- WS is control/notification only; claim/execute/submit stay HTTP (idempotent, proven) — the socket buys latency, not a second transport.
- One heartbeat per interval, never both: main loop skips HTTP POST while `ws_connected` is set; the socket thread owns cadence (same policy-derived availability payload).
- Resumed mid-sprint session from opencode DB (`ses_ed7bb365...`, Sprint 16 done + Sprint 17 WIP: `apply_heartbeat` refactor + `ws_registry.py` already started); continued from there.
**Next steps:**
- Sprint 18: two-PC stress test (sustained load, throughput/failure-rate, repeated restarts).
- Two-machine E2E still pending (see quick-reference.md).

---

## 2026-10-13 — Sprint 18: Two-PC Stress Test (mocked)
**Goal:** System survives sustained workload with correct final results despite deliberate interruptions (roadmap Sprint 18). Mocked: two local workers (separate ID files) stand in for PC A/B; the real laptop run stays pending.
**Scope (in / out):**
- In: bulk-expiry unit test, live 240-unit job across 2 workers with worker-kill x2 + coordinator restart, throughput/failure/correctness measurement, attempt-outcome audit.
- Out: real-laptop run (pending, same commands as quick-reference), batch claiming / perf optimization (observed, deferred to Sprint 31), dashboard changes.
**Exit condition (verbatim from roadmap):** The system completes a large batch with correct final results despite deliberate Worker interruptions.
**Changes:**
- tests: `test_bulk_expired_leases_sweep_in_one_pass` (6 units, 3 held-then-aged leases, one sweep requeues all with attempt 2/1 split + 3 `expired` rows)
- No product-code changes needed: leases, sweep-on-claim, 409 tolerance, WS reconnect, and coordinator restart recovery all held under load.
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 276 passed
- random order → 276 passed
- Live (fresh DB, lease 8s, A `--interval 0.5 --execution-delay 10`, B `--interval 0.5`): 240-unit hello_compute job → **completed 240/240, failed 0, final=28920** (= 240*241/2) in 403.7s (0.59 units/s) despite kill-A 12s, kill-B 8s, and a coordinator restart mid-drain — pass
- Attempt audit: 32 `expired` (straggler/killed units redone by the survivor), 239 `completed`, 2 NULL-outcome rows (open attempts, likely kill-window orphans — units themselves all completed; noted, not chased for prototype)
**Decisions:**
- Late submits from the straggler rarely 409'd because hello_compute values are deterministic (identical resubmit → 200 per Sprint 7) — the expiry path still proved itself via the 32 swept attempts.
- Throughput note for Sprint 31: ~1.5s effective per-unit cadence per worker (0.2s CPU sample + telemetry/claim/submit roundtrips + 0.5s tick sleep); batch claiming would be the obvious lever. No change now — correctness first.
- Live orchestration stayed a temp script (uncommitted); dev DB untouched (fresh `live18.db`, removed after).
**Next steps:**
- Sprint 19: internet prototype (hosted coordinator, TLS, outbound worker, remote logging).
- Two-machine E2E still pending (see quick-reference.md).

---

## 2026-10-13 — Sprint 19: Internet Prototype (TLS loop, mocked)
**Goal:** Move beyond LAN: hosted coordinator, TLS, outbound-only worker, env config, remote logging (roadmap Sprint 19). Mocked locally: no second network available, so the TLS + outbound path is proven against a local https coordinator; real cross-network run stays pending.
**Scope (in / out):**
- In: dev-cert generator, worker `--ca-bundle`/`--insecure` through every HTTP client + wss socket, uvicorn TLS serving, WS peer logging, env examples, live https/wss proof.
- Out: worker authentication/enrollment (explicitly Sprint 20 — no tokens/credentials here), production CA/VPN setup, dashboard changes.
**Exit condition (verbatim from roadmap):** The two computers can be in different networks and still participate in the same compute pool. — NOT yet demonstrated (single network); the transport it depends on (TLS + outbound-only) is proven. Carried explicitly, not claimed.
**Changes:**
- NEW scripts/gen_dev_cert.py (self-signed SAN cert via openssl → cryptography → manual PS instructions; refuses to overwrite)
- Worker: config.get_tls_verify (insecure wins, else bundle-or-platform-store), `verify` param on register/heartbeat/claim/submit/telemetry/capabilities/ping clients, ws_client.build_ssl_context + ca_bundle/insecure through ws_loop (ssl only for wss), main.py `--ca-bundle`/`--insecure` (+ loud warning) wired everywhere
- Coordinator: WS connect log gains peer IP (remote-ops visibility); TLS itself terminates at uvicorn (no app change); version → 0.1.0-sprint19
- tests: test_tls.py (13: verify matrix, per-client forwarding, wss mapping, context shapes); 12 existing httpx fakes gained `verify` passthrough
- .env.example (https URL + TLS notes), quick-reference TLS section, README status
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 289 passed
- random order → 289 passed
- Live (fresh DB, uvicorn `--ssl-certfile/keyfile` :8443): worker `--ca-bundle` loop → online over https, wss control socket up with zero HTTP heartbeats; 4-unit job → **completed, final=10**; `--insecure --once` registers with warning — pass
**Decisions:**
- Auth boundary respected per AGENTS.md: transport trust only, no identity/credentials (Sprint 20 owns that). `--insecure` is dev-LAN-only and says so every run.
- Outbound-only confirmed by construction: worker opens all connections (https + wss); coordinator never dials out. No inbound worker ports needed.
- Remote logging = coordinator-side logs (uvicorn access + heartbeat/result lines incl. WS peer); no new pipeline — stated, not built.
**Next steps:**
- Sprint 20: worker authentication (enrollment tokens, credential rotation, revocation).
- Cross-network E2E pending (needs hosted coordinator or VPN + real certs).

---

## 2026-10-14 — Sprint 20: Worker Authentication
**Goal:** Trusted worker identity — enrollment, bearer credentials, rotation, revocation; unregistered workers get no work, revoked workers lose access (roadmap Sprint 20).
**Scope (in / out):**
- In (Full Sprint 20): hash-only credential tables, enrollment mint/redeem (single-use + TTL), bearer dependency on all worker-write routes + WS `?token=`, worker credential.json + `--enroll` CLI + headers everywhere, rotation/revocation, 17+7 tests.
- Out: operator auth for mint/revoke endpoints (single-node prototype: local operator), credential expiry schedules, mTLS.
**Exit condition (verbatim from roadmap):** An unregistered Worker cannot receive Work Units. A revoked Worker loses access.
**Changes:**
- Coordinator: models/auth.py (enrollment_tokens, worker_credentials — hashes only), services/auth.py (mint/redeem/verify/rotate/revoke/list), schemas/auth.py, api/api_auth.py (mint/list/enroll/rotate/revoke/credential views), api/deps.py (Bearer dependency + body-capture middleware), main.py mounts router + middleware, config AUTH_ENABLED=false default, authenticate wired on register/heartbeat/capabilities/claim/result/resources, WS `?token=` check (4401 close codes: missing/bad/other-worker/revoked), version → 0.1.0-sprint20
- Worker: worker/credentials.py (credential.json beside ID, tolerant load, enroll client), Bearer headers on every client, WS URL token param, `--enroll` CLI (saves + exits), enrolled worker_id wins over local UUID, 401 fail-fast hints ("re-enroll") instead of silent retries
- tests: coordinator test_auth.py (17: mint/redeem/replay/TTL/hashed-storage/enabled-blocks/valid-passes/cross-worker/revoke/rotate/6×WS), worker test_credentials.py (9) + test_auth_wiring.py (7); 25 existing httpx fakes gained `**kw` tolerance
- docs: quick-reference auth section, .env.example AUTH_ENABLED, .gitignore credential.json, README status
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 322 passed
- random order → 322 passed
- Live (AUTH_ENABLED=true): anonymous claim → **401**; `--enroll` → credential saved; enrolled worker completes 4-unit job (final=10); revoke → claim **401** — pass
**Decisions:**
- Prior in-progress auth draft (models/service/schemas/endpoints/deps/tests) was reviewed and kept — it was well-designed (hash-only, single-use, per-call revocation). The missing piece was integration: router never mounted (the 11-test failure), no route wiring, no WS check, no worker side.
- Fixed a real tz bug in the draft: `_aware()` stripped tzinfo instead of adding UTC → naive/aware comparison crash on TTL-aged tokens.
- WS auth via `?token=` (sockets can't rely on Authorization headers); mismatch binds token→worker, never cross-identity.
- Default `AUTH_ENABLED=false` keeps the entire anonymous LAN dev flow (all 289 prior tests) green untouched.
**Next steps:**
- Sprint 21: security boundary prototype (workload allowlist, resource limits, temp dirs, signed manifests) (done below).
- Cross-network E2E still pending (needs hosted coordinator or VPN + real certs).

---

## 2026-10-14 — Sprint 21: Security Boundary Prototype
**Goal:** Prepare for outside-origin workloads; worker refuses anything over-declared or tampered (roadmap Sprint 21).
**Scope (in / out):**
- In (Full Sprint 21): shared HMAC seal package, submit-time allowlist, sealed claims, worker verification + refusal, per-unit temp dirs, execution time-box, traversal guard, static no-network/no-subprocess scan, refusal tests.
- Out: OS-level confinement/cgroups/syscall filtering (Sprint 22), asymmetric manifests (later), audit pipeline beyond access + security logs.
**Exit condition (verbatim from roadmap):** A Worker refuses a workload that exceeds declared capabilities or violates policy.
**Changes:**
- Shared: packages/protocol/signing.py (canonical-JSON HMAC seal, DEV key, tamper-evident field set) + test_signing.py (8, in pytest testpaths now)
- Coordinator: config WORKLOAD_SIGNING_KEY (+ startup warning on dev default), workloads KNOWN_WORKLOAD_TYPES + JobCreate validator (422 fail-fast), claim attaches manifest_signature, main.py 422-envelope sanitizer (default=str — a real crash bug the validator exposed)
- Worker: worker/security/ (boundary docs, safe_join), registry.run_unit hardened (seal check → tempdir → timed execute; never raises), --work-root/--unit-time-limit CLI
- tests: coordinator test_security.py (7: allowlist, seal validity, tamper, duplicates, startup warning), worker test_worker_security.py (11: refusal without execution, timeout, cleanup, safe_join, import scan, missing-root)
**Tests run:**
- full suite both orders → 346 passed
- Live: unknown-type submit → 422 JSON envelope; signed job completes (final=10); flipped-range assignment refused locally; dev-key warning in coordinator log — pass
**Decisions:**
- Shared-secret HMAC now, public-key manifests later — stated as integrity-not-origin in code + worklog.
- Caught live: missing work root crashed the worker loop (FileNotFoundError escaped run_unit's never-raises contract) → run_unit returns failed units for env failures + main.py creates the root. Regression test added.
- Caught by tests: ThreadPoolExecutor.__exit__ joins hung threads (defeats timeouts) → daemon-thread + join(timeout) instead; abandoned threads documented, preemptive kill deferred to Sprint 22.
- Caught before commit: test_basename collision (test_security.py × 2) — worker file renamed test_worker_security.py.
**Next steps:**
- Sprint 22: sandboxed execution (real isolation layer) (done below).
- Cross-network E2E still pending (needs hosted coordinator or VPN + real certs).

---

## 2026-10-15 — Sprint 22: Sandboxed Execution
**Goal:** A real execution isolation layer; least-complex acceptable boundary (roadmap Sprint 22).
**Scope (in / out):**
- In (Full Sprint 22): platform evaluation with evidence, Job Object limits + low-integrity child, stdio-JSON runner, run_unit sandboxed path + --sandbox CLI, boundary/parity tests, live sandboxed job.
- Out: read/network kernel denial (needs AppContainer/elevation — absent here), mandatory gating (S23 decision), Docker route (not installed, grey-licensed on Home).
**Exit condition (verbatim from roadmap):** A test workload cannot access protected Worker/user resources outside its sandbox.
**Changes:**
- NEW worker/sandbox/ (native.py ctypes, launch.py suspended-start, runner.py JSON stdio child, sandbox.py orchestrator): low-integrity token (S-1-16-4096 via AllocateAndInitializeSid), Job Object (memory/process caps, kill-on-close), granted Low-label work dir, one-sample-per-tick unchanged
- registry.run_unit(sandboxed=True) + main.py --sandbox; capabilities.sandbox flag (worker + coordinator schemas)
- tests: test_sandbox_execution.py (16: roundtrip, 3-workload parity, tamper refusal, timeout, cleanup, memory-cap kill, setup-failure mapping, unknown-type)
**Tests run:**
- full suite both orders → 364 passed (incl. 16 sandbox)
- Live: --sandbox worker completes 4-unit job (final=10); log reports "job-object-only" boundary honestly; greedy-200MB-under-48MB child killed by the job (test); canary write-denial needs elevation — recorded, not claimed
**Decisions:**
- AppContainer profiles REJECTED with evidence: CreateAppContainerProfile absent from this build's advapi32 (ctypes + .NET P/Invoke both confirm; Win11 Home restricted).
- Low-integrity tokens need elevation (SetTokenInformation → 998 unelevated; SeTcb/SeAssignPrimary/SeCreateToken all NOT HELD) → integrity layer is opt-in/degraded-loud, never silent.
- What IS enforced here: process isolation, memory/process caps, kill-on-close, write-denial only when elevated. Reads + network remain open — stated in code, quick-reference, and here.
- ctypes handle-truncation class of bugs hit three times (pseudo-handle err 6, SetInformationJobObject in kernel32 not advapi32, SID arg counts) → explicit restype/argtypes block now standard in native.py.
**Next steps:**
- Sprint 23: verification sampling + reputation (done below).
- Public registration stays CLOSED per the roadmap gate (this milestone is "satisfactory" for the prototype threat model only).

---

## 2026-10-15 — Sprint 23: Work Verification & Reputation
**Goal:** Untrusted workers become measurable — wrong output is detected and the score drops (roadmap Sprint 23).
**Scope (in / out):**
- In (Full Sprint 23): append-only reputation_events, Laplace-smoothed reliability service, hooks on submit/sweep/duplicates/conflicts, GET /workers/{id}/reputation, tests.
- Out: scheduling use of scores (S31), dashboard display (follow-up), slashing/economics (S27+).
**Exit condition (verbatim from roadmap):** A Worker producing intentionally incorrect output is detected and its reliability score decreases.
**Changes:**
- Coordinator: models/reputation.py (5 event kinds, evidence-not-verdict), services/reputation.py (score=(pos+1)/(total+2), MIN_EVIDENCE=5, unrated below), work.py hooks (accepted/rejected+kind on submit, expired on sweep, agreed on confirm, disagreed on overturn + 409-conflict), api/workers.py GET reputation endpoint, version → 0.1.0-sprint23
- tests: test_reputation.py (8: unrated, 404, smoothing, exit-condition, expiry, agree, disagree, bad-event)
- quick-reference.md (reputation section), README status
**Tests run:**
- full suite both orders → 372 passed
- Live: honest worker 6/6 accepted → score 0.875; lying worker 6 rejections (all value_mismatch) → score 0.125 — pass
**Decisions:**
- Score is always derived from the event log, never stored — the formula can evolve without migrations.
- Idempotent resubmits record nothing (no new evidence, no double count); 409 conflicts record disagreement against the submitter.
- MIN_EVIDENCE=5 keeps new workers near-prior (0.5) instead of 0%/100% extremes; unrated workers stay eligible (never punished for being new).
- Duplicate comparison happens before verification in submit_result, so agreement on already-verified originals is cheap and safe.
**Next steps:**
- Sprint 24: worker packaging (Windows installer, tray, auto-start, updates) (done below).
- Cross-network E2E still pending (needs hosted coordinator or VPN + real certs).

---

## 2026-10-15 — Sprint 24: Worker Packaging
**Goal:** Another person can install the worker — no dev environment, joins the test network (roadmap Sprint 24).
**Scope (in / out):**
- In (Full Sprint 24): --setup wizard, PySide6 tray (loop in QThread), HKCU auto-start, --log-file, --check-update (check-only), worker.spec + build script, uninstall script, docs/privacy.md, tests.
- Out: signed MSIX installer, in-place auto-update downloads, windowed build.
**Exit condition (verbatim from roadmap):** A clean Windows machine can install the Worker without a development environment and join the test network.
**Changes:**
- Worker: setup_wizard.py (--setup: URL, enrollment token, idle/CPU policy, autostart), tray.py (QSystemTrayIcon + WorkerThread, pure helpers tested), autostart.py (HKCU Run, no elevation; data_dir helper), main.py (--setup/--tray/--install-autostart/--remove-autostart/--log-file/--check-update), requirements +PySide6/pyinstaller
- Build: apps/worker/worker.spec (one-dir console, UPX off — AV false-positive call), scripts/build_worker.ps1, scripts/uninstall_worker.ps1, docs/privacy.md
- tests: test_packaging.py (13: wizard defaults/custom/bad-CPU, autostart roundtrip on temp key, tray helpers, update 0/2/1, log-file tee)
- .gitignore already covers dist//build/ (shared Node patterns)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests packages/protocol -p no:randomly` → 385 passed
- `pip install pyside6` → 6.12.0; `npm run build` untouched (dashboard unchanged)
- Build: PyInstaller 6.19 → dist/worker (~190MB with Qt; 13MB without); exe `--help` + live `--once` register against local coordinator (no venv) — pass
- Tray imports under pytest (helpers only; no QApplication in tests)
**Decisions:**
- UPX off: packed community binaries trigger AV heuristics; size is not our constraint.
- Update = check-only (exit 0/2/1): silent auto-install without signing infra would violate the Sprint 21/22 trust posture.
- Worker __version__ bumped 0.1.0-sprint2 → sprint24 (was stale; --check-update compares it to the coordinator version).
- Auto-start is HKCU (per-user, no elevation); uninstall never self-deletes (documented manual last step).
**Next steps:**
- Sprint 25: contributor experience (guided onboarding, limits UI, one-screen status) (done below).
- Cross-network E2E + laptop install-from-bundle still pending (needs second machine).

---

## 2026-10-15 — Sprint 25: Contributor Experience
**Goal:** Joining understandable and safe — scan, estimate, configure, pause (roadmap Sprint 25).
**Scope (in / out):**
- In (Full Sprint 25): capability estimate module, bandwidth_mbps policy + rolling enforcement, policy_summary in capabilities (both schemas), extended --setup chain, --status CLI, dashboard limits display, tests.
- Out: dashboard settings editing (needs policy-push channel — a real feature, later), sub-HTTP bandwidth shaping, onboarding GUI.
**Exit condition (verbatim from roadmap):** A non-developer can understand what is being shared, configure limits, and pause participation.
**Changes:**
- Worker: capability_estimate.py (class buckets, plain-language lines, workload fit notes), policy/bandwidth.py (60s rolling ledger, injectable clock), policy schema +bandwidth_mbps, engine bandwidth gate (cap-aware), main.py ledger per loop + byte accounting on claim/result + --status screen, setup_wizard.py full chain (scan → estimate → 8 policy questions → join), capabilities policy_summary (worker + coordinator schemas, discovery)
- Dashboard: ContributorView "Contribution limits" row + formatPolicy()
- tests: test_contributor_experience.py (16: buckets, lines, hours parse, full wizard flow, bandwidth cap, ledger math/rollover/negatives, engine gate, summary exclusion of paused)
**Tests run:**
- full suite both orders → 401 passed; `npm run build` → pass
- Live: piped-answer --setup (scan → estimate → policy → join guidance) exit 0; --status shows id/reachability/participation/limits/cache/sandbox; schedule gate correctly reported "holding (hour 18 outside 9-17)"; dashboard builds with the limits row
**Decisions:**
- Bandwidth enforcement is byte-accounting + claim-delay (same fail-closed gate shape); payloads are KB-scale so the mechanism is the deliverable — stated in code.
- Policy summary excludes `paused` (status surfaces it) and secrets (there are none in policy, but the exclusion is structural).
- Dashboard shows limits read-only; editing stays local by design (no policy-push channel exists — inventing one here would be scope creep with security implications).
- Wizard answers are positional; every question has a safe default so Enter-only works end to end.
**Next steps:**
- Sprint 26: private community beta, mocked as a local swarm (done below).
- Cross-network E2E + laptop install-from-bundle still pending (needs second machine).

---

## 2026-10-15 — Sprint 26: Private Community Beta (mocked swarm)
**Goal:** Several independently-controlled machines join/leave/fail/reconnect and contribute with zero DB intervention — mocked as isolated processes (roadmap Sprint 26).
**Scope (in / out):**
- In (Full Sprint 26, mocked): capacity endpoint, version distribution + optional 426 gate, per-worker lease cap, --diagnostics redacted bundle, beta_swarm.py harness, docs/beta.md runbook, dashboard capacity strip.
- Out: real second machines/networks, public enrollment, dashboard settings editing, download-and-install auto-update.
**Exit condition (verbatim from roadmap):** Several independently controlled computers can join, leave, fail, reconnect, and contribute without manual database intervention.
**Changes:**
- Coordinator: api/network.py GET /network/capacity (cores/RAM/GPUs by tier+vendor/cached/runtimes/versions/queue), config MIN_WORKER_VERSION ("") + MAX_LEASES_PER_WORKER (8), claim refuses outdated (426 OutdatedWorker) + hoarders ({} past cap), settings_override accepts arbitrary keys
- Worker: main.py --diagnostics (id/version/coordinator/credential-presence/policy/capabilities/sandbox/log tail; secret never printed)
- Harness: scripts/beta_swarm.py (N isolated homes, kill mid-job, operator pause/resume, API-only assertions)
- Docs: docs/beta.md (invite/monitor/maintain/offboard runbook + what-mocked-means), quick-reference beta section, README status
- Dashboard: NetworkView CapacityStrip (cores, RAM, GPUs, versions)
- tests: test_beta.py (6: rollup, empty pool, versions, 426 gate, gate passthrough, lease cap), test_diagnostics.py (3)
**Tests run:**
- full suite both orders → 410 passed; `npm run build` → pass
- Live swarm (3 workers, 12 units): all joined; pc2 killed mid-job; pc3 paused+resumed via API; job **completed 12/12**; summary 3 online + 12/5m; capacity 3 online / 18 cores / queue 0 — pass
**Decisions:**
- Mocked = isolated processes, not threads: separate IDs/policies/caches/logs, real kills — the closest single-machine proof of the exit condition; cross-machine networking explicitly still pending.
- Lease cap (8) and version gate (off by default) are guardrails, not policy: hoarding returns {} (retryable), outdated returns 426 (actionable message), neither punishes reputation.
- Diagnostics prints credential *presence*, never the value — support bundles must be forwardable without redaction steps.
- Capacity endpoint counts online workers only for resources (offline capacity isn't capacity).
**Next steps:**
- Sprint 27: compute accounting (per-unit auditable contribution records) (done below).
- Cross-network E2E + laptop install-from-bundle still pending (needs second machine).

---

## 2026-10-15 — Sprint 27: Compute Accounting
**Goal:** Measure contribution accurately — every completed unit leaves auditable data (roadmap Sprint 27).
**Scope (in / out):**
- In (Full Sprint 27): contribution_records table, v1 time estimation, availability fraction, per-worker summary, ledger + summary endpoints, overturn voiding.
- Out: credits/payouts (S28+ consume this ledger), kWh estimates, customer billing views.
**Exit condition (verbatim from roadmap):** Every completed Work Unit produces auditable contribution data.
**Changes:**
- Coordinator: models/accounting.py (append-only rows; voided_at is the one allowed mutation), services/accounting.py (estimate_times, record_completion idempotent, void_record, availability_fraction from heartbeat gaps, worker_summary), work.py hooks (record on accept, void on overturn), api/network.py GET /accounting/entries (job/worker/limit filters), api/workers.py GET /workers/{id}/accounting
- tests: test_accounting.py (12: estimates, record shape, gpu split, no-record-on-fail, no-double-count, overturn void, filters, summary reconcile, availability none/dense/gap)
- quick-reference.md (ledger section), README status
**Tests run:**
- full suite both orders → 422 passed
- Live: CPU job (2 units, gpu=0.0) + GPU-required job (2 units, gpu>0) → 4 ledger rows, all verified; DB confirms 4 units / 0.112ms / gpu 0.033; summary reconciles — pass
**Decisions:**
- v1 estimation stated plainly in code: cpu = wall (single-threaded saturating), gpu = wall iff job required GPU else 0. Refine when per-unit device telemetry exists.
- Availability = heartbeat coverage fraction (gap > 2x timeout = offline); no heartbeats = None (unknown, not zero).
- Overturn voids rather than deletes (audit trail); idempotent resubmits never double-count.
**Next steps:**
- Sprint 28: compute credits (earn/spend non-cash ledger on top of accounting).
- Cross-network E2E + laptop install-from-bundle still pending (needs second machine).




---

## 2026-10-15 - Sprint 28: Compute Credits
**Goal:** Non-cash credits that make contribution and consumption accountable (roadmap Sprint 28).
**Scope (in / out):**
- In (Full Sprint 28): append-only credit_ledger, earn on verified original completion, spend on job submit, 402 shortfall, per-worker totals + ledger endpoints.
- Out: cash/payouts, market pricing, resource-weighted rate card, refunds/escrow, credit transfers.
**Exit condition (verbatim from roadmap):** Contributors earn credits for verified work and spend them to submit jobs.
**Changes:**
- Coordinator: models/credit.py (CreditEntry; append-only; reasons earn_verified_unit/spend_job_submit), services/credits.py (balance from SUM, totals, earn_verified_unit, spend_job_submit stages debit, ledger, InsufficientCredits, CREDITS_PER_UNIT=1), work.py hook (earn on verified original; duplicates/self-deals pay 0), jobs.py create_job (checks affordability, stages debit, commits job+units+ledger atomically so a 402 never orphans a job), schemas/job.py + models/job.py + db additive column submitter_worker_id, api/jobs.py 402/404 mapping, api/workers.py GET /workers/{id}/credits, api/network.py GET /credits/ledger
- tests: test_credits.py (11: earn math, failed earns nothing, self-dealing earns nothing, spend deducts, shortfall 402 with no orphan, unknown submitter 404, anonymous free, ledger audit, balance==ledger SUM, no partial deduction, self-deal writes nothing)
- quick-reference.md (credits section), README status
**Tests run:**
- full suite both orders -> 433 passed
- Live (real coordinator + real worker on this PC): worker completed 4 open-pool units -> balance 4/earned 4/spent 0; submitter job of 3 -> balance 1/spent 3; job of 5 -> 402 {need:5,have:1} with no job created; /credits/ledger 5 rows; SQLite GROUP BY reason -> earn 4/+4, spend 1/-3, SUM=1 - pass
**Decisions:**
- Balance is never stored: it is always SUM(amount) over the append-only ledger; corrections are new rows, never edits.
- Spend is charged upfront per unit and is not refunded v1 (failed units still cost scheduling); the 402 surface states need/have.
- Self-dealing (completing a unit on a job you submitted) earns 0 - otherwise a worker could wash-mint credits; the submit still costs, so net is negative.
- Debit is staged (not committed) by spend_job_submit and committed with the job so a shortfall cannot leave a half-created job.
**Next steps:**
- Sprint 29+: consume credits in the dashboard/payout accounting views.
- Cross-network E2E + laptop install-from-bundle still pending (needs second machine).

---

## 2026-10-15 - Sprint 29: Customer API Prototype
**Goal:** Expose compute programmatically so a separate client can use the network without the dashboard (roadmap Sprint 29).
**Scope (in / out):**
- In (Full Sprint 29): customer API key auth (its own trust domain), POST /api/v1/jobs, GET /api/v1/jobs/{id}, GET /api/v1/jobs/{id}/results, GET /api/v1/usage, plus operator customer/key management.
- Out: full customer identity/authorization/isolation, signed workload defs, per-job quotas (Sprint 30); billing/payments (Sprint 28 credits are worker-only; customers run free).
**Exit condition (verbatim from roadmap):** A separate test client can submit a supported workload without using the dashboard.
**Changes:**
- Coordinator: models/customer.py (Customer, CustomerApiKey - hash-only keys, prefix for display), services/customers.py (create/issue_key/verify_key fails closed/rotate/revoke/list/owns_job/usage), schemas/customer.py (CustomerJobRequest separate from JobCreate; response models), api/customer_api.py (router prefix /api/v1; require_customer bearer dependency), Job.customer_id (additive column + db migration), services/jobs.create_job(customer_id=...), main.py router wiring
- tests: test_customer_api.py (11: key shown once, rotate invalidates old, revoke, 401 without/bad key, worker token rejected as customer key, submit+poll, results+aggregate, cross-customer 404, unknown workload 422, usage rollup, no customer credit charge)
- quick-reference.md (customer API section), README status
**Tests run:**
- full suite both orders -> 444 passed
- Live (real coordinator + real worker, separate HTTP client): minted customer; no-key/bad-key -> 401; submitted hello_compute (4 units) via /api/v1/jobs; other customer -> 404; worker completed all 4; /results final=10 values [1,2,3,4]; /usage {jobs:1, units:4, completed:4}; no spend row in credit ledger - pass
**Decisions:**
- Customer API is a separate trust namespace: keys live in their own table (own hash namespace) and a worker bearer token never authorizes /api/v1 (verified by test).
- Ownership from the key only: Job.customer_id is set by the API layer, never client-supplied; reading another customer's job returns 404 (no existence leak).
- Free community pool: customer jobs carry no submitter_worker_id and write no credit spend; usage is recorded, not billed (architecture 21 - no real money in the prototype).
- Operator customer/key endpoints are unauthenticated in the prototype, consistent with Sprint 20 enrollment-token minting; hardening lands with Sprint 30 customer identity.
**Next steps:**
- Sprint 30: customer workload isolation - customer identity, job authorization, signed workload definitions, input/output isolation, per-job quotas.
- Cross-network E2E + laptop install-from-bundle still pending (needs second machine).

---

## 2026-10-16 - Sprint 30: Customer Workload Isolation
**Goal:** Make each customer a true tenant - own jobs, own results, bounded resources, and a workload contract the worker can independently verify (roadmap Sprint 30).
**Scope (in / out):**
- In: GET /api/v1/me, GET /api/v1/jobs (own only), GET /api/v1/workloads (signed), GET /api/v1/quota; per-customer submit quotas; job authorization via an isolation service; signed workload definitions carried on every assignment and re-verified by the worker; job records workload_version + isolation_scope.
- Out: on-disk per-tenant namespaces (isolation at the API/DB boundary; per-unit temp dirs unchanged), billing/payments, execution budgets, multi-tenant secrets/key rotation of workload signing keys.
**Exit condition (verbatim from roadmap):** Customer A cannot access Customer B's workload or data.
**Changes:**
- packages/protocol/workloads.py (WorkloadDefinition, WORKLOAD_CATALOG hello_compute/stats_range/embeddings v1, definition_for, canonical_definition, sign_definition, verify_definition, attach_signed_definition); test_workloads.py (sign/verify roundtrip, tamper, order-independent canonicalization, no-op for unknown types)
- Coordinator: services/isolation.py (scopes, job_scope, authorize_job, AccessDenied), services/quotas.py (limits/usage/in_flight/check_submit, QuotaExceeded), config.py (CUSTOMER_MAX_UNITS_PER_JOB/IN_FLIGHT_JOBS/UNITS_IN_FLIGHT), models/job.py + db additive columns workload_version/isolation_scope, services/workloads/__init__.py (definition/workload_version/signed_manifest), services/jobs.create_job pins version+scope, schemas/work.py WorkAssignment + workload_version/workload_signature, services/work.py signs the assignment definition, schemas/customer.py (MeOut/JobSummary/WorkloadManifestOut/QuotaOut), api/customer_api.py (me, jobs list, workloads, quota, quota enforcement 413/429, authorize_job on status/results)
- Worker: execution/registry.py re-derives the local definition for catalog types and fails closed on version mismatch / bad definition signature (non-catalog types still gated by the registry allowlist); worker tests updated to attach signed definitions
- Tests: test_isolation.py (9: me, suspended key 401, signed manifests verify, pinned version/scope, A-cannot-read-B job+results 404, listing scoped, results never leak, operator job invisible), test_quotas.py (5: units-per-job 413, in-flight-jobs 429, units-in-flight 429, per-customer independence, /quota limits+usage), test_workload_definition.py (5: valid executes, version mismatch refused, missing/bad signature refused, non-catalog allowlisted)
- quick-reference.md (isolation+quota section), README status
**Tests run:**
- full suite both orders -> 468 passed
- Live (real coordinator + real worker, separate HTTP client; caps per_job=2/in_flight_jobs=5/units_in_flight=3): GET /me; GET /workloads signed manifests verified against local catalog; 3-unit submit -> 413 units_per_job; 2-unit job ran to completion (final=3, values [1,2]); B -> 404 on A's job+results and empty job list; second 2-unit submit -> 429 units_in_flight; GET /quota caps+usage consistent - pass
**Decisions:**
- Signed definitions are a separate field on the assignment (workload_version + workload_signature); the Sprint 21 manifest seal and protocol version are untouched, so no protocol break.
- Quotas are coordinator-side and enforced at submit only (413 for units-per-job, 429 for in-flight jobs/units); no execution-time budgets in the prototype.
- Input/output isolation is at the API+DB boundary (tenant-scoped queries + authorize_job -> 404 on foreign jobs); per-unit temp work dirs already isolate on disk, so no per-tenant path namespaces yet.
- Worker re-derives its own definition rather than trusting the coordinator's: a divergent contract version or signature never executes (fail closed).
- Foreign-job access returns 404, not 403, so job existence does not leak across tenants.
**Next steps:**
- Sprint 31+: surface quotas/usage in the dashboard; workload signing-key management (rotate/separate from the assignment seal); sandbox hardening before any public enrollment.
- Cross-network E2E + laptop install-from-bundle still pending (needs second machine).

---

## 2026-10-16 - Sprint 31: Scheduling Optimization
**Goal:** Move beyond FIFO - rank compatible work units with a weighted, explainable scheduling score (roadmap Sprint 31).
**Scope (in / out):**
- In: `app/services/scoring.py` (weighted score over architecture §10 inputs), wired into `claim_next_unit` (best score, FIFO tie-break); `SCORING_*` settings; score breakdown added to `GET /jobs/{job_id}/compatibility/{worker_id}`; deterministic benchmark test (scored vs FIFO).
- Out: worker protocol changes (no location/bandwidth fields - scoring is coordinator-derived only; the location term stays neutral until workers report one); dashboard UI; push/matching scheduler rewrite (still worker-pull).
**Exit condition (verbatim from roadmap):** The scheduler measurably improves throughput or reduces transfer overhead compared with FIFO.
**Changes:**
- Coordinator: services/scoring.py (component functions capability_fit/estimated_speed/cached_model/reliability/availability/transfer_cost/location_penalty; `score`, `worker_context`, `score_with_context`, `rank`), services/work.py `_select_candidate` replaces the Sprint-15 cache-first loop (compat filter first, then score all eligible, FIFO tie-break; SCORING_ENABLED=false -> eligible[0]), api/jobs.py explain now returns a `score` breakdown, api/work.py docstring, config.py SCORING_* weights + references + scoring_enabled
- Tests: test_scoring.py (15: component unit tests, rank tie-break, explain breakdown, claim prefers cached-model unit, SCORING_ENABLED=false falls back to FIFO, incompatible worker neither scores nor claims, and the FIFO-vs-scored transfer benchmark)
- quick-reference.md (scheduling score section), README status
**Tests run:**
- full suite both orders -> 483 passed
- Live (real coordinator + real worker): worker with model m1 cached; submitted plain (older) then model (newer) job; explain plain total=1.750/cached 0.0 vs model total=3.750/cached 1.0/transfer 0.0; claim returned the *newer model* job (scoring beat FIFO); real worker completed a job end-to-end under the scored scheduler - pass
- Benchmark (deterministic, in test_scoring.py): 4 workers (1 model-cached) + 6 units (3 needing m1) -> FIFO transfers 3 model downloads, scoring 1, same makespan
**Decisions:**
- Worker-pull preserved: the score orders the units *this* worker is compatible with; worker-level terms (speed/reliability/availability) are constant within one claim, so the per-unit discriminators are capability fit, cached model, and transfer cost (documented in the module).
- Compatibility still gates first (compat.check unchanged); scoring never sends work to an incompatible worker, only orders eligible units.
- FIFO (`created_at, sequence`) is the tie-break so equal scores reproduce the Sprint-9 behaviour exactly, and `SCORING_ENABLED=false` restores plain FIFO - a live A/B lever.
- Coordinator-derived inputs only: no worker protocol/schema change. The worker-reported `cached_models` plus reputation/accounting (already stored) supply every term; the `location` term is future-ready but neutral.
- Weights are settings with deliberately simple prototype defaults (architecture §10 "do not over-engineer scoring during the two-node prototype"); the model is pure and unit-tested.
**Next steps:**
- Sprint 32: large-scale simulation - simulated workers (100 -> 1,000,000) to stress scheduler + DB/queue; reuse scoring for worker-selection measurement.
- Surface scheduling score/weights in the dashboard; let operators tune weights safely.
- Cross-network E2E + laptop install-from-bundle still pending (needs second machine).
