# Security & Sandboxing Review (Sprint 35)

Scope: the coordinator, the worker, and the boundaries between them, as they
exist for the **private/invited prototype beta**. This is a self-review of the
prototype, not a third-party audit. It exists to make the public-enrollment
go/no-go decision evidence-based (`docs/public-beta-readiness.md`).

## 1. Trust boundaries

| Boundary | Assumption today | Public-beta implication |
| --- | --- | --- |
| Contributor PC | **Untrusted.** May be misconfigured, hostile, or compromised. | Same, but now you don't know the person. |
| Customer job | **Untrusted input.** Malformed params, oversized ranges. | Same. |
| Network | **Trusted LAN, plain HTTP.** | Would be untrusted + TLS required. |
| Coordinator | Trusted operator service. | Same. |
| Operator endpoints | Unauthenticated in the prototype. | Must be locked down before exposure. |

## 2. Threat model (what we defend against)

- **Malicious worker**: returns fabricated or corrupted results, hoards leases,
  floods the API, runs workloads it wasn't assigned.
- **Malicious/broken customer**: submits malformed or oversized jobs, probes
  another tenant's data.
- **Network attacker**: reads or tampers with assignments/results in transit.
- **Compromised credential**: a stolen worker or customer token is used by
  someone else.
- **Supply chain**: a forged workload definition or a replaced worker binary.

Out of scope for the prototype: multi-tenant host compromise, side-channel
attacks, a malicious coordinator operator.

## 3. Controls inventory

| Control | Status | Evidence |
| --- | --- | --- |
| Worker identity (persistent UUID, never hostname) | present | `apps/worker/worker/identity.py`; protocol `WorkerRegistration` |
| Bearer authentication, hashes only server-side | present | `apps/coordinator/app/api/api_auth.py`, `models/auth.py` |
| Credential revocation / rotation | present | `POST /workers/{id}/revoke`, `/rotate-credential`; enforced per request in `api/deps.py` |
| Signed work assignments (HMAC over sealed fields) | present | `packages/protocol/signing.py`; startup warns on dev key |
| Declarative requirements + fail-closed worker | present | `services/compat.py`; worker validates version/type/limits/policy before executing |
| Duplicate verification of sampled units | present | `models/work_unit.py:verify_of`; S8 |
| Result integrity (deterministic recompute) | present | `services/workloads/*` `expected`/`output_hash` |
| Resource limits (unit time, leases, quotas) | present | `lease_duration_seconds`, `max_leases_per_worker`, customer quotas (S30) |
| Sandboxed execution (Job Object child) | present (Windows) | `apps/worker/worker/sandbox/`; `--sandbox` |
| Filesystem isolation (per-unit temp dirs) | present | worker `--work-root`; no user-document access by construction |
| Allowlisted workloads only | present | `packages/protocol/workloads.py`; unknown type rejected |
| Customer isolation / tenant scoping | present | `/api/v1` trust domain; `Job.isolation_scope` (S29/S30) |
| Audit trail | present | `contribution_records`, `credit_ledger`, `reputation_events`, request logs |
| TLS | **gap** | prototype serves plain HTTP |
| API rate limiting / abuse detection | **gap** | none |
| Operator endpoint auth | **gap** | operator routes are unauthenticated in the prototype |
| Worker auto-update | partial | `--check-update` + `MIN_WORKER_VERSION` gate; manual reinstall |

## 4. Sandboxing review

The worker's hardened path (`worker --sandbox`) runs exactly one work unit in a
child process created **suspended** and then constrained:

- **Job Object limits** — a child process tree with CPU/memory ceilings, so a
  runaway unit is killed rather than taking the machine down.
- **Low-integrity token** (when available) — the child cannot write outside its
  per-unit temporary directory.
- **Per-unit work root** — created for the unit and cleaned up afterward; the
  workload never sees the contributor's home directory.
- **Preemptive timeout** — the unit is terminated when it exceeds its time
  limit (registered-executor-only execution in the non-sandboxed path is a
  documented prototype limitation).

What the sandbox does **not** yet provide, and why public enrollment needs it:

- **Network isolation** — a unit has the network access of the worker process.
  Public workloads must be able to be run with no outbound network.
- **Linux parity** — the Job Object / integrity mechanism is Windows-specific.
  A Linux worker needs cgroups/namespaces (or containers) before it is
  trustworthy.
- **Seccomp/content policy** — no syscall filtering or malware scanning.

For the invited beta this is acceptable because **every workload is a
deterministic, network-free, allowlisted pure-compute stub**; no arbitrary
customer code runs. The moment a real AI/arbitrary workload is added, the
network-isolation and Linux gaps become release blockers.

## 5. Privacy review

See `docs/privacy.md` (contributor-facing). Summary of the data boundary:
hardware profile, heartbeats (utilization/temps/battery/policy flag), and
computed results. No files, no keystrokes, no screenshots, no window titles,
no inbound ports. Logs stay local. This is consistent with the trust model.

## 6. Findings and required fixes before public enrollment

1. **TLS everywhere** (cert issuance, pinning/verification, no plaintext
   fallback) — public-networking task.
2. **Network-isolated execution** for real workloads.
3. **Rate limiting + automated abuse detection** on worker- and customer-facing
   routes.
4. **Operator endpoint authentication** (revoke, pause, prune, enrollment).
5. **Linux sandbox parity** before non-Windows contributors run real work.
6. **Real worker auto-update** (or a strict, enforced minimum-version policy).

None of these are needed for a **trusted, invited, allowlisted** beta on a
trusted network, which is the decision recorded in
`docs/public-beta-readiness.md`.
