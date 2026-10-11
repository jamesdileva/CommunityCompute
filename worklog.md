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
- Sprint 4: heartbeats & availability (endpoint, loop, last-seen → online/offline, basic utilization reporting).
