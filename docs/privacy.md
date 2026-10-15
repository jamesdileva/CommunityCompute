# Privacy — CommunityCompute Worker (Sprint 24)

Plain-language summary of what the worker does with your machine and your data.
The short version: **it shares spare compute, never your files, and you can
stop it instantly at any time.**

## What the worker sends to the coordinator

- **Hardware profile** (once at startup, refreshed when it changes): CPU model
  and core counts, RAM totals, GPU model/VRAM/driver, OS version, installed
  workload runtimes. This is how the scheduler sends you work your machine
  can actually run. No serial numbers, no MAC addresses, no user names.
- **Heartbeats** (every ~20s): CPU/RAM/GPU utilization, temperature when the
  driver exposes it, battery state, and whether your policy currently allows
  work. This is how the coordinator knows you are alive and what you allow.
- **Work results**: the computed outputs of assigned work units (numbers,
  hashes, embedding vectors) plus timing metrics. Results are deterministic
  and verifiable — the coordinator recomputes the expected answer.
- **Logs stay local** unless you share them: console/file logs live on your
  machine (`worker.log` beside the install, or `--log-file <path>`).

## What the worker NEVER does

- Never reads your documents, photos, browser data, or any user files.
  Sprint 21+ workloads run with an explicit allowlist, per-unit temp
  directories, and refusal paths for anything unexpected.
- Never opens inbound network ports. The worker only makes **outbound**
  connections to the coordinator you configured.
- Never runs with elevated privileges for normal operation (auto-start uses
  your own per-user login entry, no admin rights).
- Never sends keystrokes, screenshots, window titles, or process lists.
  Idle detection uses only "seconds since last input" (a single number).

## Your controls (immediate, no questions asked)

- **Pause now**: tray menu → Pause, `worker --pause`, or dashboard Pause.
  The worker stops claiming new work at once; the coordinator shows `paused`.
- **Limit sharing**: `policy.json` (idle-only, CPU/GPU caps, temperature
  ceiling, battery rules, allowed hours) — see `quick-reference.md`.
- **Auto-start**: on only if you enabled it during `--setup` (or
  `--install-autostart`); remove any time with `--remove-autostart`.
- **Uninstall**: run `scripts/uninstall_worker.ps1` (kills the worker,
  removes auto-start, optionally wipes id/policy/credential/models/logs),
  then delete the folder. Nothing else remains on a stock install.

## Credentials

Enrollment gives this machine a random bearer token (`credential.json`
beside the worker id). It proves *this machine* to the coordinator and
nothing else. If a machine is lost or shared, the operator revokes it
(`POST /workers/{id}/revoke`) and it stops working immediately. Deleting
`credential.json` + the worker id file fully de-registers the machine
locally; ask the operator to revoke the server side too.
