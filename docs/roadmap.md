# Community AI Compute Network — Sprint Roadmap

**Starting point:** Two personal computers  
**Prototype hardware:** One PC with approximately 4 GB GPU VRAM + one laptop using Intel Iris Xe graphics  
**Primary objective:** Prove that heterogeneous consumer computers can cooperate as a useful distributed compute network.

---

# Roadmap Philosophy

The project should grow in layers:

```text
Local
  ↓
Two-node distributed
  ↓
Reliable distributed
  ↓
AI workload
  ↓
Internet-connected
  ↓
Trusted community
  ↓
Public network
  ↓
Compute marketplace
```

Every sprint ends with a concrete verification/end-goal.

Do not advance because code exists. Advance because the previous layer works.

---

# Sprint 0 — Project Definition & Environment

## Goals

- Create repository.
- Establish development environments.
- Confirm both computers can communicate.
- Record hardware baselines.
- Establish coding/documentation conventions.

## Tasks

- Create Git repository.
- Create project structure.
- Install Python.
- Install Node/Vite.
- Install FastAPI dependencies.
- Install React/TypeScript dependencies.
- Install SQLite tooling.
- Record CPU/RAM/GPU information for both PCs.
- Test LAN communication.
- Create `.env.example`.
- Create initial README.

## Verification / End Goal

Both machines can communicate over the local network and the repository can run a minimal coordinator and worker process.

**Exit condition:**

```text
PC A ──> Coordinator
PC B ──> Coordinator
```

---

# Sprint 1 — Coordinator Skeleton

## Goals

Create the central control service.

## Tasks

- FastAPI application.
- `/health`.
- Basic configuration.
- SQLite connection.
- SQLAlchemy models.
- Worker table.
- Basic logging.
- API error handling.

## Verification / End Goal

Opening `/health` proves the coordinator is alive and connected to SQLite.

---

# Sprint 2 — Worker Skeleton

## Goals

Create a Worker process capable of connecting to the Coordinator.

## Tasks

- Worker configuration.
- Persistent Worker ID.
- Coordinator URL configuration.
- Registration endpoint.
- Worker startup sequence.
- Worker shutdown handling.

## Verification / End Goal

Both computers appear in:

```text
GET /workers
```

with unique Worker IDs.

---

# Sprint 3 — Hardware Capability Discovery

## Goals

Teach Workers what hardware they have.

## Tasks

- CPU discovery.
- RAM discovery.
- OS discovery.
- GPU discovery.
- VRAM discovery.
- Driver/API information.
- Capability schema.
- Capability persistence.

## Verification / End Goal

Dashboard/API shows different capability profiles for the two machines.

Example:

```text
Worker A
GPU: 4GB

Worker B
GPU: Intel Iris Xe
```

No manual hardware entry is allowed.

---

# Sprint 4 — Heartbeats & Availability

## Goals

Know whether Workers are alive and available.

## Tasks

- Heartbeat endpoint.
- Worker heartbeat loop.
- Last-seen timestamps.
- Online/offline state.
- Runtime resource information.
- Basic CPU/GPU utilization reporting.

## Verification / End Goal

Stopping a Worker causes the Coordinator to eventually mark it offline.

Restarting it returns it to online status.

---

# Sprint 5 — Job Model

## Goals

Introduce Jobs and Work Units.

## Tasks

- Job model.
- Work Unit model.
- Job creation.
- Work Unit generation.
- Job/work-unit relationships.
- State machine.
- Job status endpoint.

## Verification / End Goal

Submitting:

```text
1,000 units
chunk size = 100
```

creates exactly:

```text
10 Work Units
```

with correct ranges/identifiers.

---

# Sprint 6 — First Distributed Workload

## Goals

Execute work across both PCs.

## Tasks

- Create deterministic demo workload.
- Worker polling.
- Work assignment.
- Work execution.
- Result upload.
- Result persistence.
- Job aggregation.

## Verification / End Goal

One submitted Job is divided across both PCs and produces one correct final result.

This is the **first major project milestone**.

---

# Sprint 7 — Work Unit Leasing

## Goals

Make the network tolerate worker failure.

## Tasks

- Lease ID.
- Lease timestamps.
- Lease expiration.
- Attempt records.
- Requeue behavior.
- Duplicate result handling.

## Verification / End Goal

Start a Job, kill one Worker during execution, and confirm its unfinished Work Units are eventually completed by the other Worker.

---

# Sprint 8 — Result Verification

## Goals

Ensure Workers return correct results.

## Tasks

- Deterministic expected results.
- Output hashing.
- Result validation.
- Failure classification.
- Optional duplicate execution.

## Verification / End Goal

A deliberately corrupted result is rejected.

A correct result is accepted.

---

# Sprint 9 — Scheduler Compatibility

## Goals

Stop treating every machine as identical.

## Tasks

- Workload requirements.
- CPU requirements.
- RAM requirements.
- GPU requirement.
- VRAM requirement.
- Runtime requirement.
- Compatibility filter.

## Verification / End Goal

Create two Work Unit types:

```text
CPU-only
GPU-required
```

The scheduler sends each only to compatible Workers.

---

# Sprint 10 — Hardware Tiers

## Goals

Formalize capability classes.

## Tasks

- H1/H2/H3 model.
- Resource capability scoring.
- GPU capability normalization.
- CPU capability normalization.
- Capability report.

## Verification / End Goal

The two prototype machines receive different hardware capability profiles and the scheduler can explain why a Work Unit is or is not compatible.

---

# Sprint 11 — Contributor Policy Engine

## Goals

Let users control when their machine contributes.

## Tasks

- Idle-only mode.
- CPU percentage limit.
- GPU percentage limit where technically feasible.
- Temperature ceiling.
- Battery policy.
- Scheduled availability.
- Pause/resume.

## Verification / End Goal

When a configured condition occurs, the Worker stops accepting new work.

Pressing Pause immediately prevents additional work from being assigned.

---

# Sprint 12 — Resource Monitoring

## Goals

Make Workers continuously aware of local conditions.

## Tasks

- CPU monitoring.
- GPU monitoring.
- RAM monitoring.
- VRAM monitoring.
- Temperature monitoring.
- Process/activity detection.
- Resource telemetry.

## Verification / End Goal

Run a high-load application and observe the Worker automatically transition from available to unavailable/throttled according to policy.

---

# Sprint 13 — Workload Adapter System

## Goals

Separate the scheduler from workload implementation.

## Tasks

- `WorkloadExecutor` interface.
- Workload registry.
- Workload metadata.
- Capability checks.
- Prepare/execute/verify/cleanup lifecycle.

## Verification / End Goal

Two different workload implementations run through the same scheduler without scheduler-specific branching.

---

# Sprint 14 — First Real AI Workload

## Goals

Introduce actual AI computation.

## Preferred options

Start with one:

- Embeddings
- Small model inference
- Transcription
- Image generation

Embeddings or batch inference are recommended for the first AI workload.

## Tasks

- Model/runtime integration.
- Model requirements.
- AI Work Unit definition.
- Batch processing.
- Result validation.
- Performance measurement.

## Verification / End Goal

A real AI Job is divided into multiple Work Units and processed by the available compatible machines.

---

# Sprint 15 — Model Cache

## Goals

Avoid downloading large models repeatedly.

## Tasks

- Model manifest.
- Model version.
- Local model cache.
- Cache status reporting.
- Scheduler preference for cached Workers.
- Cache cleanup policy.

## Verification / End Goal

The first Work Unit downloads a model.

Subsequent Work Units reuse the local model without downloading it again.

---

# Sprint 16 — Dashboard

## Goals

Make the system understandable.

## Contributor view

Show:

- Online/offline.
- CPU.
- GPU.
- VRAM.
- RAM.
- Temperature.
- Current work.
- Pause.
- Contribution statistics.

## Network view

Show:

- Worker count.
- Available workers.
- Queued Work Units.
- Running Work Units.
- Completed Work Units.
- Failed Work Units.
- Throughput.

## Verification / End Goal

A user can visually understand what both PCs are doing without inspecting logs.

---

# Sprint 17 — WebSocket Control Plane

## Goals

Move from basic polling toward responsive coordination.

## Tasks

- Worker WebSocket connection.
- Heartbeat over persistent connection.
- Work notifications.
- Pause/cancel messages.
- Connection recovery.

## Verification / End Goal

A newly available Worker receives a work notification without requiring aggressive polling.

---

# Sprint 18 — Two-PC Stress Test

## Goals

Prove the system survives sustained workload.

## Tasks

- Generate hundreds/thousands of small Work Units.
- Run both PCs.
- Measure throughput.
- Measure failure rate.
- Measure scheduling overhead.
- Test repeated Worker restarts.
- Test coordinator restart.

## Verification / End Goal

The system completes a large batch with correct final results despite deliberate Worker interruptions.

---

# Sprint 19 — Internet Prototype

## Goals

Move beyond LAN.

## Tasks

- Hosted development Coordinator.
- Secure outbound Worker connection.
- TLS.
- Worker authentication.
- Environment configuration.
- Remote logging.

For initial testing, use a private network/VPN if necessary rather than exposing an insecure Coordinator.

## Verification / End Goal

The two computers can be in different networks and still participate in the same compute pool.

---

# Sprint 20 — Worker Authentication

## Goals

Establish trusted Worker identity.

## Tasks

- Enrollment tokens.
- Worker credentials.
- Credential rotation.
- Revocation.
- Authenticated API.
- Authenticated WebSocket.

## Verification / End Goal

An unregistered Worker cannot receive Work Units.

A revoked Worker loses access.

---

# Sprint 21 — Security Boundary Prototype

## Goals

Prepare for workloads originating outside the developer's own machines.

## Tasks

- Workload allowlist.
- Resource limits.
- Temporary work directories.
- Filesystem restrictions.
- Network restrictions.
- Process restrictions.
- Signed workload manifests.

## Verification / End Goal

A Worker refuses a workload that exceeds declared capabilities or violates policy.

---

# Sprint 22 — Sandboxed Execution

## Goals

Create a real execution isolation layer.

## Tasks

Evaluate:

- Containers
- Windows sandboxing
- restricted subprocesses
- VM isolation
- WASM for suitable workloads

Choose the least complex mechanism that provides an acceptable security boundary.

## Verification / End Goal

A test workload cannot access protected Worker/user resources outside its sandbox.

**Do not open public registration before this milestone is satisfactory.**

---

# Sprint 23 — Work Verification & Reputation

## Goals

Make untrusted Workers measurable.

## Tasks

- Known-answer tasks.
- Verification sampling.
- Duplicate execution.
- Worker reliability score.
- Failure rate.
- Reputation history.

## Verification / End Goal

A Worker producing intentionally incorrect output is detected and its reliability score decreases.

---

# Sprint 24 — Worker Packaging

## Goals

Turn the Worker into something another person can install.

## Tasks

- Windows installer.
- Configuration wizard.
- Tray application.
- Auto-start option.
- Update mechanism.
- Uninstall.
- Logs.
- Privacy explanation.

## Verification / End Goal

A clean Windows machine can install the Worker without a development environment and join the test network.

---

# Sprint 25 — Contributor Experience

## Goals

Make joining understandable and safe.

## Tasks

Onboarding:

```text
Install
 ↓
Hardware scan
 ↓
Capability estimate
 ↓
Contribution policy
 ↓
Join
```

Settings:

- idle-only
- temperature
- CPU
- GPU
- schedule
- bandwidth
- pause

## Verification / End Goal

A non-developer can understand what is being shared, configure limits, and pause participation.

---

# Sprint 26 — Private Community Beta

## Goals

Invite a small number of trusted participants.

## Tasks

- Enrollment system.
- Worker versions.
- Monitoring.
- Support logs.
- Abuse controls.
- Basic documentation.
- Network capacity dashboard.

## Verification / End Goal

Several independently controlled computers can join, leave, fail, reconnect, and contribute without manual database intervention.

---

# Sprint 27 — Compute Accounting

## Goals

Measure contribution accurately.

## Tasks

Track:

- Work Units completed.
- execution time.
- GPU time estimate.
- CPU time estimate.
- successful work.
- verified work.
- availability.
- reliability.

## Verification / End Goal

Every completed Work Unit produces auditable contribution data.

---

# Sprint 28 — Compute Credits

## Goals

Introduce non-cash internal economics.

## Tasks

- Contributor credit balance.
- Compute consumption.
- Credit issuance rules.
- Credit deduction.
- Anti-abuse limits.

Example:

```text
Contribute 10 verified compute units
        ↓
+10 credits

Use 4 compute units
        ↓
-4 credits
```

## Verification / End Goal

A contributor can earn compute credits and later spend them on a workload.

---

# Sprint 29 — Customer API Prototype

## Goals

Expose compute programmatically.

## Tasks

- API authentication.
- Job submission.
- Workload requirements.
- Status.
- Result retrieval.
- Usage accounting.

Example:

```text
POST /api/v1/jobs
GET  /api/v1/jobs/{id}
GET  /api/v1/jobs/{id}/results
```

## Verification / End Goal

A separate test client can submit a supported workload without using the dashboard.

---

# Sprint 30 — Customer Workload Isolation

## Goals

Separate contributor trust from customer trust.

## Tasks

- Customer identity.
- Job authorization.
- Signed workload definitions.
- Input isolation.
- Output isolation.
- Per-job resource quotas.

## Verification / End Goal

Customer A cannot access Customer B's workload or data.

---

# Sprint 31 — Scheduling Optimization

## Goals

Move beyond FIFO.

## Tasks

Scheduling score based on:

- capability fit
- estimated performance
- cached model
- reliability
- availability
- network transfer cost
- resource policy
- geographic/latency constraints

## Verification / End Goal

The scheduler measurably improves throughput or reduces transfer overhead compared with FIFO.

---

# Sprint 32 — Large-Scale Simulation

## Goals

Test million-node-like behavior without owning million machines.

## Tasks

Build simulated Workers.

Simulated attributes:

```text
GPU
VRAM
CPU
RAM
bandwidth
availability
reliability
location
```

Simulate:

- 100
- 1,000
- 10,000
- 100,000
- 1,000,000 nodes

## Verification / End Goal

Scheduler behavior and database/queue architecture remain measurable under large simulated node counts.

---

# Sprint 33 — Multi-Workload Network

## Goals

Support multiple independent AI workload types.

Potential workloads:

- embeddings
- inference
- image generation
- transcription
- video frame processing
- audio processing
- agent subtasks

## Verification / End Goal

Different hardware classes simultaneously process different workload types through one shared scheduler.

---

# Sprint 34 — Economics Research

## Goals

Determine whether the network can economically compete with existing compute providers.

Measure:

- contributor electricity cost
- GPU depreciation
- bandwidth
- worker uptime
- utilization
- verification overhead
- customer price
- network infrastructure cost

Compare against centralized compute.

## Verification / End Goal

Produce a measured cost-per-useful-compute model.

No assumptions about profitability should survive this sprint without data.

---

# Sprint 35 — Public Beta Readiness

## Goals

Determine whether public participation is responsible.

Checklist:

- Security review.
- Sandboxing review.
- Privacy review.
- Abuse controls.
- Worker auto-update.
- Credential revocation.
- Monitoring.
- Incident handling.
- Terms/privacy documentation.
- Data retention policy.
- Customer isolation.

## Verification / End Goal

A documented go/no-go decision for public worker enrollment.

---

# Sprint 36 — Public Community Network

## Goals

Open controlled registration.

## Tasks

- Website.
- Worker download.
- Registration.
- Contributor dashboard.
- Network dashboard.
- Supported workload catalog.
- Documentation.
- Support/diagnostics.

## Verification / End Goal

An outside participant can:

```text
discover project
→ download Worker
→ install
→ configure contribution
→ join
→ receive approved work
→ earn contribution credit
```

without developer assistance.

---

# Sprint 37 — Paid Compute Experiment

## Goals

Test whether external customers will pay.

## Tasks

- Pricing model.
- Customer accounts.
- Usage tracking.
- Payment provider.
- Contributor accounting.
- Network fee.

## Verification / End Goal

A controlled customer can pay for a supported workload and the system can calculate contributor/network compensation.

---

# Sprint 38 — Marketplace

## Goals

Create the full two-sided network.

```text
Contributors
     ↓
Community Compute Pool
     ↑
Customers
```

## Verification / End Goal

Supply and demand operate independently:

- contributors provide capacity
- customers submit jobs
- scheduler matches them
- verified compute is accounted for
- economics settle correctly

---

# Sprint 39 — Advanced Distributed Workloads

## Goals

Explore W2 workloads.

Potential work:

- coordinated pipelines
- distributed fine-tuning
- larger batch inference
- multi-stage AI workflows

## Verification / End Goal

At least one W2 workload demonstrates useful distributed execution without unacceptable coordination overhead.

---

# Sprint 40+ — W3 Research

## Goals

Investigate tightly coupled distributed AI.

Questions:

- Can consumer Internet bandwidth support useful model parallelism?
- Can compression reduce communication?
- Can locality-aware scheduling help?
- Can nodes form high-bandwidth clusters?
- Can nearby machines cooperate as micro-clusters?

## Verification / End Goal

Do not define success as "we made it work."

Success is a measured comparison against a centralized GPU.

If distributed execution is slower or more expensive, document why.

---

# Major Milestones

## M1 — Distributed Compute Proven

Completed after Sprint 6.

```text
2 PCs
 ↓
Work Units
 ↓
Distributed execution
 ↓
Correct result
```

## M2 — Fault Tolerant

Completed after Sprint 8.

Workers can disappear and work can recover.

## M3 — Heterogeneous Compute

Completed after Sprint 10.

Different hardware receives appropriate work.

## M4 — AI Compute

Completed after Sprint 14.

Real AI workloads run through the distributed system.

## M5 — Internet Compute

Completed after Sprint 20.

Independent networks can participate securely.

## M6 — Safe Community Compute

Completed after Sprint 26.

Outside participants can safely contribute through packaged Workers.

## M7 — Compute Economy

Completed after Sprint 29/28.

Credits and API-based compute consumption exist.

## M8 — Commercial Experiment

Completed after Sprint 37.

A real customer can purchase compute.

## M9 — Community AI Cloud

Completed after Sprint 38.

The system is a genuine two-sided distributed compute marketplace.

---

# The Most Important Rule

The project should **not** attempt to jump from:

```text
2 PCs
```

to:

```text
1,000,000 GPUs
```

architecturally.

Instead prove each abstraction:

```text
2 physical nodes
      ↓
10 simulated nodes
      ↓
100 simulated nodes
      ↓
1,000 real/simulated nodes
      ↓
private community
      ↓
public community
      ↓
commercial network
```

The core abstraction remains:

```text
Job
 ↓
Work Units
 ↓
Capability Matcher
 ↓
Worker Lease
 ↓
Execution
 ↓
Verification
 ↓
Result
```

If that loop remains correct as the network grows, the rest of the infrastructure can evolve around it.

---

# Final Prototype Definition

The first version does **not** need to be impressive.

It needs to prove:

> **Two ordinary computers with different hardware can contribute their available resources to a shared compute pool, receive work appropriate to their capabilities, execute independent Work Units, return verified results, and gracefully recover when one computer disappears.**

Once that works, the "community-powered AI cloud" stops being merely an idea and becomes a measurable engineering project.
