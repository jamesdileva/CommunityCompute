# Community AI Compute Network — Architecture

**Status:** Baseline architecture for a two-node prototype  
**Primary goal:** Build a community-powered distributed compute network that turns idle consumer PCs into a pool of AI/compute workers.

---

## 1. Vision

The system allows people to voluntarily contribute spare CPU/GPU capacity.

A contributor installs a Worker application. The Worker detects hardware capabilities, monitors availability, receives compatible work units, executes them locally, returns results, and pauses/throttles when the user needs the machine.

The network exposes the resulting capacity as a distributed compute service.

Core principle:

> **Do not ask whether a machine is powerful. Ask what useful work the machine can safely and efficiently perform.**

The first prototype uses two heterogeneous low/mid-range PCs. The architecture must be capable of growing from 2 nodes to thousands or millions without requiring a redesign of the fundamental worker/job model.

---

## 2. Goals

### Prototype goals

- Connect two PCs over a network.
- Install a Worker on each machine.
- Discover CPU/GPU/RAM/VRAM/software capabilities.
- Benchmark enough to establish useful capability information.
- Register each node with a Coordinator.
- Submit a batch workload.
- Split the workload into independent work units.
- Schedule compatible work units across both nodes.
- Execute work locally.
- Return results.
- Retry failed/interrupted work.
- Pause work when the contributor becomes active.
- Demonstrate heterogeneous scheduling.

### Long-term goals

- Public Internet participation.
- Large heterogeneous worker pools.
- Secure sandboxed execution.
- Workload capability matching.
- Dynamic resource/availability reporting.
- Work verification.
- Contributor rewards or compute credits.
- Customer/API access.
- Commercial compute marketplace.
- Multiple workload classes.
- Regional/network-aware scheduling.
- Strong privacy and security guarantees.

### Non-goals for the first prototype

- Training one huge model across both machines.
- Splitting a large LLM across consumer machines.
- Cryptocurrency/blockchain.
- Real-money payouts.
- Public Internet worker execution.
- Production-grade multi-tenant security.
- Million-node scale.

---

## 3. Key Architectural Principle: Work Units

A Job is a logical workload.

A Job is decomposed into Work Units.

A Work Unit is the smallest independently executable piece of work that a Worker can complete and report.

Examples:

- 100 generated images.
- 100 video frames.
- A batch of audio files.
- A batch of embeddings.
- One independent inference request.
- A dataset shard.
- An agent subtask.

The scheduler assigns **work units**, not vague jobs.

Example:

```text
Job: generate 1,000 images

Work Unit 1  -> images 1-100
Work Unit 2  -> images 101-200
...
Work Unit 10 -> images 901-1000
```

This enables heterogeneous hardware to contribute without pretending that every GPU is interchangeable.

---

## 4. Workload Tiers

### W1 — Independently Executable

Best initial target.

Examples:

- Batch inference
- Image generation
- Video frame processing
- Audio processing
- Embeddings
- Transcription batches
- Independent agent tasks
- Monte Carlo workloads

These are highly parallelizable.

### W2 — Distributed / Coordinated

Potential future support.

Examples:

- Some fine-tuning workloads
- Larger batch inference
- Pipeline workloads
- Workflows requiring limited synchronization

### W3 — Tightly Coupled

Future/research area.

Examples:

- Large model parallelism
- Distributed training requiring frequent GPU communication
- Large LLM inference split across nodes

W3 should not be a prototype target because Internet latency/bandwidth can overwhelm the computational benefit.

---

## 5. Hardware Capability Tiers

Hardware tiers are separate from workload tiers.

Example:

- H1: low-end / constrained
- H2: mid-range
- H3: high-end

A node can have different strengths across resources.

Example:

```text
Node A
GPU: H1
CPU: H2
RAM: H2
Network: H2

Node B
GPU: H2
CPU: H1
RAM: H2
Network: H1
```

The scheduler matches actual capability requirements rather than simply assigning a global "power score."

---

## 6. Capability Profile

Each Worker maintains a capability profile.

Suggested fields:

### Hardware

- CPU model
- CPU logical cores
- CPU physical cores when available
- CPU architecture
- RAM total
- GPU vendor
- GPU model
- GPU VRAM
- GPU compute capability/API
- GPU driver
- GPU memory currently available
- Storage capacity
- Storage throughput estimate

### Software

- OS
- Worker version
- Supported execution runtimes
- CUDA/ROCm/Metal/DirectML/etc. capabilities
- Installed/supported model runtimes
- Container/sandbox capabilities

### Runtime state

- GPU utilization
- CPU utilization
- RAM utilization
- GPU temperature
- power state when available
- current availability
- current workload
- estimated free capacity
- last heartbeat

### Policy

Contributor-defined constraints:

- Idle-only
- Maximum CPU percentage
- Maximum GPU percentage
- Temperature ceiling
- Allowed hours
- Pause while gaming/fullscreen application is detected
- Pause on battery
- Bandwidth limits
- Storage limits

---

## 7. System Components

```text
                        CONTROL PLANE
                 ┌─────────────────────────┐
                 │ API / Coordinator       │
                 │                         │
                 │ Job Manager             │
                 │ Scheduler               │
                 │ Capability Registry     │
                 │ Worker Registry         │
                 │ Result/Job State        │
                 │ Authentication          │
                 └────────────┬────────────┘
                              │
                    WebSocket/HTTP
                              │
             ┌────────────────┼────────────────┐
             │                │                │
        ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
        │ Worker A│      │ Worker B│      │ Worker N│
        │         │      │         │      │         │
        │ Scanner │      │ Scanner │      │ Scanner │
        │ Monitor │      │ Monitor │      │ Monitor │
        │ Executor│      │ Executor│      │ Executor│
        │ Sandbox │      │ Sandbox │      │ Sandbox │
        └─────────┘      └─────────┘      └─────────┘
             │                │                │
           GPU/CPU          GPU/CPU          GPU/CPU
```

---

## 8. Control Plane

The Control Plane is the network's coordination layer.

Prototype components:

- FastAPI API
- Scheduler service
- SQLite database
- WebSocket worker connection
- Simple web dashboard

Production evolution:

- PostgreSQL
- Redis/NATS/message broker
- Dedicated scheduler workers
- Object storage
- Metrics system
- Authentication service
- Regional coordinators
- Queue partitioning

The Control Plane should not execute untrusted customer workloads.

---

## 9. Worker

The Worker is a local daemon/desktop application.

Responsibilities:

1. Discover hardware.
2. Register with Coordinator.
3. Maintain heartbeat.
4. Report availability.
5. Receive work.
6. Validate work requirements.
7. Download required assets.
8. Execute inside the permitted environment.
9. Monitor resources.
10. Pause/cancel when user policy requires it.
11. Checkpoint when possible.
12. Upload result.
13. Report metrics.
14. Clean temporary data.

The Worker should fail closed: if a workload exceeds declared limits or the local environment cannot satisfy requirements, it rejects the work instead of attempting execution.

---

## 10. Scheduler

The Scheduler receives pending work units and available Worker profiles.

A simplified compatibility process:

```text
1. Is Worker online?
2. Is Worker currently available?
3. Does required OS/runtime exist?
4. Does GPU vendor/API match?
5. Is required VRAM <= available VRAM?
6. Is CPU requirement satisfied?
7. Is RAM requirement satisfied?
8. Does contributor policy allow this job?
9. Is network/storage capacity sufficient?
10. Is the estimated execution worthwhile?
```

Only compatible workers receive the work unit.

Later, scoring can consider:

```text
score =
    capability_fit
  + estimated_speed
  + availability
  + reliability
  + network_quality
  - thermal/policy risk
  - transfer cost
```

Do not over-engineer scoring during the two-node prototype.

---

## 11. Job State Machine

Suggested states:

```text
QUEUED
  ↓
DISPATCHED
  ↓
RUNNING
  ├──→ COMPLETED
  ├──→ FAILED
  ├──→ CANCELLED
  └──→ INTERRUPTED
           ↓
        RETRY QUEUE
```

Work units should have independent state.

A Job is complete only when its required Work Units are complete.

---

## 12. Reliability

Workers are expected to disappear.

Examples:

- User closes Worker.
- Laptop sleeps.
- Game starts.
- Internet disconnects.
- GPU driver crashes.
- Worker crashes.
- User shuts down the PC.

Therefore:

- Work Units must be retryable.
- Results must be idempotent.
- Workers need heartbeats.
- Leases need expiration.
- Scheduler must reclaim expired work.
- Completed results must be recorded before a Work Unit is considered complete.

A Worker should not receive an irreplaceable one-shot task.

---

## 13. Execution Model

Initial execution should use a controlled, predefined workload runtime rather than arbitrary executable customer code.

Prototype example:

```text
Job
  └── workload_type = image_batch
      └── model = approved_local_model
          └── input batch
```

Later, workloads can be packaged using:

- OCI containers
- WASM where practical
- signed workload bundles
- restricted process execution

Security must become stricter before accepting arbitrary third-party workloads.

---

## 14. Data Flow

```text
Customer/User
    ↓
Submit Job
    ↓
API
    ↓
Job created
    ↓
Job decomposed into Work Units
    ↓
Scheduler
    ↓
Capability matching
    ↓
Worker lease
    ↓
Worker downloads inputs/model
    ↓
Local execution
    ↓
Result upload
    ↓
Verification
    ↓
Work Unit completed
    ↓
Job aggregation
    ↓
Final result
```

---

## 15. Networking

### Prototype

Use:

- REST/HTTP for API operations
- WebSocket for worker control/heartbeat
- Local network or controlled tunnel for two-machine testing

### Public evolution

Workers should make outbound connections to the Control Plane.

Avoid requiring contributors to open inbound firewall ports.

Conceptually:

```text
Worker ──outbound──> Coordinator
Worker <──commands── Coordinator
Worker ──results───> Coordinator
```

This is substantially easier for consumer deployment.

---

## 16. Storage

### Prototype

SQLite is appropriate.

Suggested logical tables:

- workers
- worker_capabilities
- worker_heartbeats
- jobs
- work_units
- work_unit_attempts
- results
- workloads
- events

### Production

Move coordination state to PostgreSQL when concurrency and availability justify it.

Large model files and job artifacts should eventually use object storage rather than the relational database.

---

## 17. Security Architecture

Security is one of the highest-risk areas.

Never assume a contributor's PC or customer workload is trusted.

Eventually require:

- Worker identity
- TLS
- short-lived job credentials
- signed workload packages
- sandbox/container isolation
- resource limits
- filesystem isolation
- network restrictions
- process restrictions
- secret isolation
- encrypted transport
- result integrity checks
- malware scanning where appropriate
- audit logs

For public participation, arbitrary code execution on contributor machines is unacceptable without strong isolation.

---

## 18. Verification

The network needs confidence that a Work Unit was actually completed correctly.

Initial approaches:

- deterministic test workloads
- expected output hashes
- known-answer test units
- redundant execution for selected work
- result metadata
- execution logs

Future:

- probabilistic verification
- redundant workers
- reputation
- attestation where available
- challenge workloads

Bitcoin-style proof-of-work is not a direct solution because AI results are not naturally verified by one universal hash puzzle.

---

## 19. Contributor Experience

The Worker should make participation extremely simple:

```text
Install
  ↓
Hardware scan
  ↓
Capability test
  ↓
Choose contribution policy
  ↓
Join network
  ↓
Worker runs in background
```

Dashboard:

- Node status
- Current workload
- GPU/CPU utilization
- Temperature
- Compute contributed
- Credits/rewards
- Pause button
- Policy controls
- Network statistics

A contributor should always be able to stop work immediately.

---

## 20. Customer Experience

Long-term:

```text
Create account
    ↓
API key
    ↓
Submit workload
    ↓
Specify requirements
    ↓
Receive job ID
    ↓
Poll/stream status
    ↓
Retrieve results
```

The customer should not care which individual machines execute the Work Units.

---

## 21. Economics

Do not implement real money in the prototype.

Future options:

### Compute credits

Contribute compute → earn credits → consume credits.

### Marketplace

Customer pays → contributor receives share → network retains fee.

### Hybrid

- free community pool
- paid priority compute
- credits
- contributor payouts

The economics should be designed after real measurements of:

- cost per useful GPU-hour
- worker uptime
- failure rate
- bandwidth cost
- electricity
- customer willingness to pay
- scheduling efficiency

---

## 22. Technology Stack

### Worker

Preferred initial stack:

- Python
- PySide6 or lightweight system-tray UI
- psutil
- GPUtil/vendor APIs where appropriate
- subprocess-based controlled execution
- HTTP client
- WebSocket client

A future Rust/Go worker may be considered for a smaller distribution footprint, but Python is preferable for prototype velocity and AI ecosystem compatibility.

### Backend

- Python
- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy 2.x
- SQLite initially

### Frontend

- React
- TypeScript
- Vite

The contributor dashboard can initially be a web dashboard. A packaged desktop UI can be added after the Worker protocol stabilizes.

### Packaging

- PyInstaller initially for Windows Worker
- Later evaluate native installers / MSIX / signed releases

### AI runtimes

Do not lock the platform to one runtime.

Design a workload adapter interface supporting future backends such as:

- Ollama
- llama.cpp
- ONNX Runtime
- PyTorch
- TensorRT
- DirectML
- CUDA
- ROCm

The prototype should use one or two controlled workloads rather than supporting everything.

---

## 23. Repository Structure

```text
community-ai-compute/
├── apps/
│   ├── coordinator/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   ├── scheduler/
│   │   │   ├── services/
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   ├── db/
│   │   │   └── main.py
│   │   └── tests/
│   │
│   ├── worker/
│   │   ├── worker/
│   │   │   ├── capabilities/
│   │   │   ├── monitoring/
│   │   │   ├── execution/
│   │   │   ├── networking/
│   │   │   ├── policy/
│   │   │   ├── storage/
│   │   │   └── main.py
│   │   └── tests/
│   │
│   └── dashboard/
│       ├── src/
│       │   ├── pages/
│       │   ├── components/
│       │   ├── services/
│       │   └── types/
│       └── tests/
│
├── packages/
│   ├── protocol/
│   ├── workload-spec/
│   └── shared-types/
│
├── workloads/
│   ├── hello-compute/
│   ├── image-batch/
│   └── video-batch/
│
├── tests/
│   ├── integration/
│   └── end_to_end/
│
├── docs/
├── scripts/
├── docker/
├── .env.example
└── README.md
```

---

## 24. Architecture Evolution

### Stage A

Two PCs on LAN.

### Stage B

Two PCs over Internet/VPN.

### Stage C

Trusted small community.

### Stage D

Public workers.

### Stage E

Commercial customer workloads.

### Stage F

Large distributed marketplace.

The protocol should remain stable while infrastructure around it evolves.

---

## 25. Critical Design Decisions

1. Work Units are the fundamental scheduling unit.
2. Hardware capability is explicit.
3. Worker availability is dynamic.
4. Jobs must tolerate worker disappearance.
5. W1 independent workloads are the initial focus.
6. The prototype will not attempt giant distributed LLM inference.
7. SQLite is acceptable for the two-node prototype.
8. FastAPI is the initial coordinator API.
9. Workers use outbound connections.
10. Public execution requires strong sandboxing.
11. Real-money economics are deferred.
12. AI runtime integrations are adapter-based.
13. Local prototype precedes public Internet deployment.
14. Security is treated as a first-class architecture concern before public workers.

