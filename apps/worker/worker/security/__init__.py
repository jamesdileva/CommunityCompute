"""Worker-side security boundary (Sprint 21 prototype).

What this package enforces today:
- allowlist: only registry-known workload types execute (`run_unit` fails
  closed on anything else — the registry IS the allowlist).
- integrity: every assignment's HMAC seal is verified before execution;
  missing/tampered seals are refused, never executed.
- time-boxing: `execute()` runs under a wall-clock limit (abandoned-thread
  semantics — documented; true preemptive kill needs the Sprint 22 sandbox).
- temp dirs: one fresh work directory per unit, always cleaned up, even on
  failure. Executors must treat it as scratch, not a privilege boundary.
- traversal guard: `safe_join` keeps workload file access inside the
  work directory (defense against `..` escapes in payloads).
- static boundary: workload code (`worker/execution/`) makes no network
  calls and spawns no processes (enforced by test, not by the OS — the OS
  part is Sprint 22's sandbox).

What it explicitly does NOT do (Sprint 22): OS-level confinement,
resource cgroups, syscall filtering, untrusted-code isolation.
"""
