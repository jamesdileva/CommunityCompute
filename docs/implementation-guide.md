# Community AI Compute Network — Implementation Guide

**Purpose:** Practical guide for turning the architecture into a working two-PC prototype.

---

# 1. Implementation Strategy

Build the smallest complete distributed loop first:

```text
Worker A ─┐
          ├──> Coordinator ──> Work Queue
Worker B ─┘
                     │
                     ▼
               Work Unit
                     │
                     ▼
                 Worker
                     │
                     ▼
                  Result
```

Do not begin with:

- payments
- public registration
- huge models
- arbitrary code execution
- Kubernetes
- blockchain
- giant distributed LLMs

The first proof is simply:

> Two different computers can safely receive different work units, execute them, and return correct results.

---

# 2. Development Environment

Recommended:

- Windows 11 for both prototype PCs if practical
- Python 3.12+ or current stable project-supported version
- Node.js LTS
- Git
- VS Code
- SQLite
- FastAPI
- React + Vite
- TypeScript

Create a single repository.

---

# 3. Phase 1 — Repository Skeleton

Create:

```text
community-ai-compute/
├── apps/
│   ├── coordinator/
│   ├── worker/
│   └── dashboard/
├── packages/
│   ├── protocol/
│   └── shared-types/
├── workloads/
├── tests/
└── docs/
```

The coordinator and worker should be independently runnable.

---

# 4. Phase 2 — Protocol First

Before building the scheduler, define the messages.

Core concepts:

### WorkerRegistration

```json
{
  "worker_id": "uuid",
  "worker_version": "0.1.0",
  "hostname": "PC-A",
  "capabilities": {}
}
```

### Heartbeat

```json
{
  "worker_id": "uuid",
  "timestamp": "...",
  "status": "idle",
  "resources": {}
}
```

### WorkUnit

```json
{
  "work_unit_id": "uuid",
  "job_id": "uuid",
  "workload_type": "demo_batch",
  "requirements": {},
  "payload": {}
}
```

### WorkResult

```json
{
  "work_unit_id": "uuid",
  "worker_id": "uuid",
  "status": "completed",
  "result": {},
  "metrics": {}
}
```

Do not overcommit to these exact JSON shapes. Put versioning around the protocol so it can evolve.

---

# 5. Phase 3 — Coordinator

Implement FastAPI.

Initial endpoints:

```text
GET  /health

POST /workers/register
POST /workers/{id}/heartbeat
GET  /workers

POST /jobs
GET  /jobs/{id}

GET  /work/{worker_id}
POST /work/{work_unit_id}/result
POST /work/{work_unit_id}/failure
```

A WebSocket channel can be introduced once polling is working.

Start simple.

---

# 6. Phase 4 — Database

SQLite schema should include at minimum:

```text
workers
worker_capabilities
worker_heartbeats

jobs
work_units
work_unit_attempts

results
events
```

Important relationships:

```text
Job
 └── Work Units
       └── Attempts
             └── Worker
```

Do not store large binary model files or generated media inside SQLite.

---

# 7. Phase 5 — Worker Registration

Worker startup:

```text
start
 ↓
load configuration
 ↓
discover hardware
 ↓
build capability profile
 ↓
register with coordinator
 ↓
start heartbeat
 ↓
monitor local resources
 ↓
request work
```

The worker should have a persistent generated node ID.

Do not use hostname as identity.

---

# 8. Phase 6 — Hardware Discovery

Start with information that is reliably available.

CPU:

- architecture
- core count
- logical processors
- approximate frequency

RAM:

- total
- available

GPU:

- vendor
- model
- VRAM
- driver
- utilization when available
- temperature when available

Do not build a complex universal GPU detector immediately.

Use adapters:

```text
GPUProvider
├── NvidiaProvider
├── AMDProvider
├── IntelProvider
└── UnknownProvider
```

A provider can return:

```python
GPUInfo(
    vendor="nvidia",
    model="...",
    vram_mb=4096,
    utilization_percent=...
)
```

---

# 9. Phase 7 — Capability Testing

Separate:

### Hardware discovery

"What do I have?"

from:

### Capability testing

"What can I actually do?"

For example:

```text
VRAM = 4 GB
```

does not automatically tell you whether a workload will perform acceptably.

Run small controlled benchmarks where appropriate.

Store:

- workload name
- runtime
- throughput
- peak memory
- failure status

Example:

```text
image_batch_v1
throughput = 0.7 units/sec
peak_vram = 3.4 GB
```

This becomes valuable scheduling information later.

---

# 10. Phase 8 — Workload Specification

Every workload should declare requirements.

Example:

```json
{
  "workload_type": "demo_compute",
  "version": "1",
  "requirements": {
    "cpu_cores": 2,
    "ram_mb": 2048,
    "gpu": false
  }
}
```

GPU example:

```json
{
  "requirements": {
    "gpu": true,
    "gpu_vendor": "nvidia",
    "min_vram_mb": 3500
  }
}
```

Requirements should be declarative.

The scheduler should not need workload-specific logic for every job.

---

# 11. Phase 9 — First Workload

Do not begin with LLMs.

Build a deterministic compute workload.

Example:

```text
Input:
numbers 1..1,000,000

Work Unit:
numbers 1..100,000

Output:
sum/hash/statistics
```

Why?

Because you can prove:

- scheduling
- distribution
- execution
- failure
- retry
- result verification

without involving model compatibility.

---

# 12. Phase 10 — Work Unit Generation

Given:

```text
Job = 1,000,000 records
chunk size = 100,000
```

create:

```text
WU-001 = 1..100,000
WU-002 = 100,001..200,000
...
WU-010 = 900,001..1,000,000
```

Each Work Unit must have a unique ID.

The original Job should remain immutable.

---

# 13. Phase 11 — Basic Scheduler

Start with FIFO.

Pseudo-flow:

```text
for pending work unit:
    find idle workers
    filter compatible workers
    choose first compatible worker
    lease work unit
```

Only after correctness is established should scoring be introduced.

---

# 14. Phase 12 — Leasing

A Work Unit should not simply be marked "running."

It should be leased.

Example:

```text
lease_id
worker_id
started_at
expires_at
attempt_number
```

If the Worker disappears:

```text
lease expires
 ↓
work unit returns to queue
 ↓
another worker receives it
```

This is fundamental to reliability.

---

# 15. Phase 13 — Worker Execution Loop

Worker:

```text
while running:

    update local state

    if user policy says unavailable:
        sleep

    ask coordinator for compatible work

    if no work:
        wait

    receive work unit

    validate requirements

    execute

    verify local result

    upload result

    report metrics
```

Never blindly execute a received workload.

Validate:

- protocol version
- workload type
- resource limits
- required runtime
- payload size
- policy

---

# 16. Phase 14 — Result Verification

For the deterministic prototype:

Coordinator knows the expected result.

Worker returns:

```text
work_unit_id
output
output_hash
execution_time
resource metrics
```

Coordinator verifies.

Later, selected jobs can be duplicated:

```text
WU-001 → Worker A
WU-001 → Worker B

Compare results.
```

Redundant execution is expensive, so it should eventually be selective.

---

# 17. Phase 15 — Two-PC Test

Use your two machines.

Example:

```text
PC A
4GB VRAM

PC B
Iris Xe
```

They should register independently.

The dashboard should show:

```text
PC A   ONLINE   GPU 4GB
PC B   ONLINE   Intel Iris Xe
```

Submit a job large enough to create many work units.

Observe both machines receiving work.

---

# 18. Phase 16 — Deliberate Failure Tests

This phase is mandatory.

While work is running:

### Test A

Kill Worker A.

Expected:

```text
Worker A disappears
 ↓
lease expires
 ↓
work is requeued
 ↓
Worker B completes it
```

### Test B

Disconnect network.

Expected:

- heartbeat stops
- coordinator eventually marks Worker offline
- active lease eventually expires

### Test C

Pause Worker.

Expected:

- Worker stops accepting new work
- current policy determines whether current work finishes or checkpoints

### Test D

Start a game or high-load application.

Expected:

- Worker detects reduced availability
- Worker throttles/pauses according to policy

---

# 19. Phase 17 — Idle Detection

Do not attempt perfect "idle" detection initially.

Use measurable signals:

```text
GPU utilization
CPU utilization
fullscreen applications
keyboard/mouse inactivity
battery state
temperature
```

Create a policy engine:

```text
AvailabilityPolicy
├── gpu_limit
├── cpu_limit
├── temperature_limit
├── battery_policy
├── schedule
└── pause_processes
```

Example:

```text
if gpu_utilization > 80%:
    pause_new_work()

if temperature > configured_limit:
    stop_work()

if fullscreen_game_detected:
    pause()
```

---

# 20. Phase 18 — Resource Throttling

The Worker should have two distinct controls:

### Scheduling availability

"Should I accept work?"

### Execution limits

"How much of my resources may the work consume?"

This distinction matters.

Example:

```text
GPU utilization currently 40%
max permitted = 60%

Worker can accept work
but workload must stay within policy
```

Future versions can implement stronger GPU/CPU controls.

---

# 21. Phase 19 — First AI Workload

Once deterministic distribution works, introduce an AI workload.

Good first choices:

1. Embeddings
2. Small inference
3. Image generation
4. Transcription

The best first AI workload is one that can be divided into independent batches.

Example:

```text
10,000 text documents
 ↓
100 batches
 ↓
100 Work Units
 ↓
Workers process batches
```

---

# 22. Phase 20 — Model Distribution

Model files can be large.

Do not send a model with every Work Unit.

Instead:

```text
Worker downloads model once
        ↓
model cached locally
        ↓
many work units reuse it
```

Worker reports:

```text
installed_workloads
cached_models
model_versions
```

Scheduler can prefer workers that already have the required model.

This can dramatically reduce bandwidth.

---

# 23. Phase 21 — Workload Adapters

Implement a generic interface:

```python
class WorkloadExecutor:
    def can_execute(self, work_unit, capabilities): ...
    def prepare(self, work_unit): ...
    def execute(self, work_unit): ...
    def verify(self, result): ...
    def cleanup(self): ...
```

Then:

```text
executors/
├── demo/
├── embeddings/
├── image_generation/
├── transcription/
└── ...
```

The scheduler remains workload-agnostic.

---

# 24. Phase 22 — Dashboard

Contributor dashboard:

```text
Node Status
GPU
CPU
RAM
Temperature
Current Job
Current Work Unit
Contribution
Pause
Settings
```

Network dashboard:

```text
Online Workers
Available GPUs
Available CPU
Queued Work
Running Work
Completed Work
Failed Work
Throughput
```

Keep the UI simple during prototype development.

---

# 25. Phase 23 — Internet Connectivity

Do this only after LAN behavior is stable.

Preferred architecture:

```text
Worker A ──outbound──┐
Worker B ──outbound──┤
Worker C ──outbound──┼──> Hosted Coordinator
Worker D ──outbound──┤
```

Avoid requiring inbound connections.

For early testing, a private VPN such as Tailscale can simplify secure multi-machine testing before exposing services publicly.

---

# 26. Phase 24 — Authentication

Add Worker credentials.

Registration:

```text
Enrollment token
 ↓
Worker identity
 ↓
Long-lived node credential
```

Use short-lived credentials for individual jobs.

Never place a master server secret inside a Worker package.

---

# 27. Phase 25 — Security Hardening

Before public participation:

- TLS everywhere
- authenticated workers
- signed workload manifests
- strict resource limits
- sandboxed execution
- filesystem isolation
- network isolation
- temporary work directories
- cleanup after jobs
- no access to user documents
- no arbitrary shell commands
- audit logging

A public Worker must be treated as security-sensitive software.

---

# 28. Phase 26 — Public Worker Beta

Only after security basics are proven:

```text
Website
 ↓
Download Worker
 ↓
Install
 ↓
Hardware scan
 ↓
Contribution settings
 ↓
Join network
```

Start with an allowlist of supported workloads.

Do not open arbitrary customer code execution.

---

# 29. Phase 27 — Reputation and Reliability

Track:

- uptime
- successful work units
- failed work units
- average execution time
- cancellation rate
- verification failures
- version
- hardware stability

Use this for scheduling.

Example:

```text
New worker
 ↓
small low-risk work
 ↓
successful history
 ↓
higher-value work eligibility
```

---

# 30. Phase 28 — Economics

Only after real network measurements.

Track:

```text
GPU-hours contributed
CPU-hours contributed
successful work
failed work
electricity estimate
customer revenue
network operating cost
```

Then decide:

- credits
- payouts
- marketplace
- hybrid

Do not promise profitability before measuring actual economics.

---

# 31. Phase 29 — Scaling Architecture

When SQLite becomes insufficient:

```text
SQLite
   ↓
PostgreSQL
```

When one scheduler becomes insufficient:

```text
Single Scheduler
   ↓
Queue + multiple schedulers
```

When artifact transfer becomes large:

```text
Coordinator
   ↓
Object Storage/CDN
```

When monitoring grows:

```text
Metrics
Logs
Tracing
```

Do not introduce distributed infrastructure before the workload requires it.

---

# 32. Testing Strategy

### Unit

- capability detection
- compatibility matching
- policy engine
- work-unit creation
- state transitions
- result verification

### Integration

- worker registration
- heartbeat
- job submission
- work leasing
- result submission

### End-to-end

Two real computers.

Test:

```text
submit
→ distribute
→ execute
→ return
→ verify
→ aggregate
```

### Failure testing

- worker crash
- network loss
- coordinator restart
- duplicate result
- expired lease
- malformed payload
- unsupported workload
- resource limit violation

---

# 33. Development Rule

At every sprint, maintain a working system.

Avoid building ten components that cannot communicate until the end.

Preferred rhythm:

```text
new component
 ↓
integrate
 ↓
test
 ↓
verify
 ↓
commit
 ↓
next component
```

---

# 34. Definition of "Prototype Complete"

The two-PC prototype is successful when:

1. Both machines register.
2. Their hardware profiles are visible.
3. A Job can be submitted.
4. Job becomes multiple Work Units.
5. Scheduler assigns compatible Work Units.
6. Both PCs execute work.
7. Results return.
8. Results are verified.
9. Results aggregate correctly.
10. One PC can disappear and its work can be retried elsewhere.
11. A Worker can pause.
12. User resource limits are respected.
13. At least one real AI workload can use the same Work Unit infrastructure.

At that point, the project has demonstrated the central idea.

