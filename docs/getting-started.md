# Getting started (participants)

This is the end-to-end guide for joining CommunityCompute as a **contributor**.
It is written so an invited participant can go from "heard about the project"
to "earning contribution credit" without contacting a developer. The beta is
**invited and allowlisted**: you need an enrollment token from the operator.

> Operator? See [Minting an enrollment token](#minting-an-enrollment-token-for-the-operator).

## 1. What you need

- A Windows 10/11 PC (other platforms can run the worker from source).
- Nothing else if you use the prebuilt bundle. From source you also need
  **Python 3.12+**.
- An **enrollment token** from the operator (single-use, one per machine).
- The **coordinator URL**, e.g. `http://192.168.1.10:8000` on your LAN.

No administrator rights are required. The worker opens **no inbound ports** —
it only makes outbound connections.

## 2. Get the worker

**Option A — prebuilt bundle (recommended).** Download `worker.exe` from the
project's release page (ask the operator for the exact build). It is
self-contained; no Python needed.

**Option B — from source.** With Python 3.12+:

```powershell
git clone https://github.com/jamesdileva/CommunityCompute
cd CommunityCompute
python apps/worker/worker/main.py --help
```

Examples below show `worker`; substitute `worker.exe` or
`python apps/worker/worker/main.py` as appropriate.

## 3. Run the setup wizard

```powershell
worker --setup
```

The wizard:

1. asks for the **coordinator URL** and the **enrollment token**;
2. scans your hardware and prints a plain-language summary plus what each
   workload would use;
3. captures your **contribution limits** (idle-only, CPU/GPU caps, temperature
   ceiling, battery policy, allowed hours, upload cap) — every answer has a safe
   default, so pressing Enter throughout is fine;
4. optionally installs **auto-start at login**.

It writes `policy.json` next to the worker's id file. You can edit it later;
changes apply within one worker tick.

## 4. Enroll this machine

Exchange the single-use token for this machine's credential:

```powershell
worker --enroll <token> --coordinator-url http://<coordinator>:8000
```

This saves a credential for the worker's persistent node ID and exits. The
token is consumed — it cannot be used again. Each machine needs its own token.

## 5. Start contributing

```powershell
worker --coordinator-url http://<coordinator>:8000 --loop
```

The worker registers, heartbeats, and picks up small work units when your
policy allows. To run it in the background with a tray icon:

```powershell
worker --tray
```

If you enabled auto-start in the wizard it will begin at your next login.

## 6. Confirm and watch your node

```powershell
worker --status            # am I contributing, right now?
worker --check-update      # am I on the current version?
```

The **dashboard** has a **My node** tab: open the dashboard, select or paste
your node id, and see live CPU/GPU/RAM, your **credit balance** (earned/spent),
reliability, current work, and availability. The same numbers are available
directly:

- `GET /workers/{id}` — status, capabilities, policy summary
- `GET /workers/{id}/credits` — `balance`, `earned`, `spent`
- `GET /workers/{id}/stats` and `/workers/{id}/accounting` — contribution
- `GET /workers/{id}/reputation` — reliability score and outcomes

Credit is a **prototype accounting unit** with no cash value in this beta.

The same catalog the website shows is available publicly at `GET /workloads`
(no auth): the supported workload types, their parameters, and the hardware
requirements a machine must meet to receive them.

## 7. Pause, resume, adjust, uninstall

```powershell
worker --pause             # stop taking new work
worker --resume
worker --remove-autostart  # stop launching at login
```

Edit `policy.json` to change limits. To uninstall, remove the worker binary,
its id/credential file, and `policy.json` (see `docs/data-retention.md`); the
operator can revoke your credential with `POST /workers/{id}/revoke`.

## 8. If something looks wrong

Run `worker --diagnostics` and send the output to the operator — it is redacted
and **never includes your credential**. See `docs/support.md` for common issues.

## Minting an enrollment token (for the operator)

The operator mints single-use tokens (kept out of band, never committed):

```powershell
# create a token (returns the token once, stores only a hash)
curl -X POST http://127.0.0.1:8000/auth/enrollment-tokens -H "Content-Type: application/json" -d "{\"note\":\"alice-laptop\"}"
# list tokens + used/unused state
curl http://127.0.0.1:8000/auth/enrollment-tokens
```

Give the token to the participant over a trusted channel with the coordinator
URL. See `docs/beta.md` and `docs/public-beta-readiness.md` for the beta
posture and what is deliberately out of scope.

## What this network is not (yet)

This is a prototype. Public enrollment is closed, TLS and rate limiting are not
deployed on this LAN build, and only allowlisted deterministic workloads run.
See `docs/public-beta-readiness.md` for the recorded decision and blockers.
