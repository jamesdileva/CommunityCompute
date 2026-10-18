# Economics (Sprint 34)

**Roadmap end goal:** *“Produce a measured cost-per-useful-compute model. No
assumptions about profitability should survive this sprint without data.”*

This document records the model, the assumptions behind it, and the numbers
measured from the live two-node prototype. It is a **research finding, not a
promise**: the model is implemented and measured, but the prototype's
workloads are deterministic stubs, so the absolute per-unit costs are
illustrative. The parts that *are* measured are called out explicitly, and
everything else is labelled an assumption.

Reproduce:

```powershell
python scripts/economics_report.py                 # human-readable
python scripts/economics_report.py --json report.json
python scripts/economics_report.py --electricity 0.30 --utilization 0.5
# or, with the coordinator running:
#   GET http://127.0.0.1:8000/economics/report
```

Code: `apps/coordinator/app/economics/{model,measure,report}.py`,
endpoint `app/api/economics.py`, driver `scripts/economics_report.py`.

---

## 1. The model

Cost of one **useful** compute unit (a credit-earning, verified original unit):

```text
contributor_cost  = Σ_class  useful_hour_cost(class, utilization) × busy_ms(class)
                    ─────────────────────────────────────────────────────────────  [÷ useful units]
useful_hour_cost  = (electricity_per_hour + depreciation_per_hour) / utilization
electricity/hour  = (idle_w + (load_w − idle_w)·u) / 1000 × price_per_kWh
depreciation/hour = acquisition_usd / life_hours
bandwidth/unit    = transfer_mb_per_unit / 1024 × price_per_GB
infra/unit        = infra_usd_per_month / measured monthly useful units
total/unit        = contributor + bandwidth + infra
```

The decisive term is **utilization**. A contributor pays electricity and
depreciation whether or not the machine is leased, so dividing the wall-clock
hour by utilization is what makes idle consumer hardware expensive — and it is
why the network only competes when sustained utilization is high. Utilization
is floored at 1% in the model so a near-idle capture does not produce an
infinite number.

Two input types are kept strictly separate:

| Kind | Where it comes from |
| --- | --- |
| **Measured** | execution time, CPU/GPU time, verified-unit volume, verification overhead, failure rate, worker hardware classes, heartbeat availability, window |
| **Assumed** | electricity price, hardware power/price/life, bandwidth price, infrastructure cost, centralized list prices |

---

## 2. Measured from the live prototype

Captured 2026-10-18 from the coordinator database after a real run
(two real workers on the RX 6400 PC + one registered CPU-only class,
36 requested units, `verify_sample=0.3`):

| Measured | Value |
| --- | --- |
| Useful (credit-earning) units | 36 |
| Executions / contribution records | 44 |
| **Verification overhead** | **×1.222** (duplicate checks re-ran 22% of units) |
| Failures | 0 (`failure_rate` 0.0) |
| Busy machine time | 1.04 ms (CPU 1.04 / GPU 0.403) |
| Mean unit / mean GPU unit | 0.0236 ms / 0.0288 ms |
| Workers by class | amd_gpu ×2, cpu_only ×1 |
| Availability (window) | 0.92 over a 0.018 h window |
| Utilization | ≈0 (machine idle >99.9% of the capture) |
| Credits | earned 36 / spent 0 |

Per-workload mean execution (all sub-millisecond stubs):

| Workload | Units | Mean ms |
| --- | --- | --- |
| hello_compute | 20 | 0.0261 |
| image_generate | 14 | 0.0288 |
| stats_range | 10 | 0.0115 |

**Read this honestly:** every execution is a fraction of a millisecond, so the
prototype demonstrates the *pipeline* (accounting, verification overhead,
credit issuance) but tells us almost nothing about the cost of real AI
compute. The verification overhead (×1.22) and the credit volume (36) are
genuine and useful; the per-unit costs are not quotable.

---

## 3. Assumptions

### Electricity, hardware, infrastructure

| Class | Idle W | Load W | Acquisition | Life (h) |
| --- | --- | --- | --- | --- |
| cpu_only | 35 | 90 | $600 | 43,800 (5 y) |
| igpu | 40 | 110 | $800 | 43,800 |
| consumer_gpu | 70 | 300 | $1,200 | 35,040 (4 y) |
| amd_gpu (prototype) | 60 | 250 | $900 | 35,040 |
| mid_gpu | 90 | 450 | $2,500 | 35,040 |
| high_gpu | 120 | 700 | $12,000 | 43,800 |

- Electricity: **$0.17/kWh** (US residential average, assumption).
- Bandwidth: **$0.00/GB** (marginal, assumed — most home connections are flat-rate).
- Infrastructure: **$40/month** (coordinator hosting + domain, assumption).
- These are overridable without code changes: env `ECONOMICS_*` or
  `--electricity/--bandwidth/--infra/--utilization` on the script.

### Centralized baselines (cited, captured 2026-10-18)

| Baseline | $/hr | Source (re-check before quoting) |
| --- | --- | --- |
| Cloud GPU, T4-class on-demand | 0.53 | AWS g4dn.xlarge on-demand list |
| Cloud GPU, A100-class on-demand | 3.06 | AWS p3.2xlarge on-demand list |
| Cloud CPU, vCPU-hour on-demand | 0.032 | GCP n1 vCPU on-demand list |

List prices move and vary by region/commitment; swap the JSON via
`ECONOMICS_CLOUD_BASELINES` before using any comparison publicly.

---

## 4. Result

At the **measured** (near-zero) prototype utilization, the owned machine looks
expensive per useful hour, exactly as the model predicts:

| Baseline | Local amd_gpu $/useful-hr | Local ÷ centralized |
| --- | --- | --- |
| T4-class ($0.53) | 3.59 | ×6.77 (costlier) |
| A100-class ($3.06) | 3.59 | ×1.17 (costlier) |

(Measured utilization ≈0 → floored to 1% → $3.59/useful-hr. This is the correct
answer for “a GPU that sits idle all day”.)

### Break-even: where owning pays off

The model's sensitivity grid over utilization and electricity price, compared
to the T4-class instance:

| Utilization \ $/kWh | 0.10 | 0.17 | 0.30 |
| --- | --- | --- | --- |
| 10% | $0.336 (0.63×) | $0.391 (0.74×) | $0.494 (0.93×) |
| 25% | $0.146 (0.28×) | $0.176 (0.33×) | $0.232 (0.44×) |
| 50% | $0.082 (0.15×) | $0.104 (0.20×) | $0.144 (0.27×) |
| 90% | $0.054 (0.10×) | $0.072 (0.14×) | $0.106 (0.20×) |

Solving `useful_hour_cost = $0.53` for the prototype amd_gpu class at
$0.17/kWh gives a **break-even utilization of ≈7%** (depreciation dominates
toward the low end). Above that, an *already-owned* consumer GPU is cheaper per
useful hour than a T4-class cloud instance; below it, the cloud wins because
you only pay while it runs.

### Verification overhead is a real cost multiplier

The capture measured ×1.22 — 22% of executions were duplicate verification
runs that earn no credits. The model folds this in by costing *all* recorded
busy time and dividing by *useful* units. If `verify_sample` rises toward 1.0,
this roughly doubles the contributor cost; it is a tunable cost/trust dial, not
a rounding error.

### CPU comparison is not like-for-like

The capture ran every unit on the GPU machine, so no CPU-only class produced
work and the vCPU-hour baseline has no local counterpart yet. Comparing a whole
desktop to a single vCPU-hour would also be apples-to-oranges (the desktop has
6 cores + a GPU). A CPU-class measurement needs a CPU-only machine.

---

## 5. What does *not* survive this sprint

- **No profitability claim.** At the prototype's measured utilization the
  network is not competitive, and the workloads are stubs. The honest statement
  is a *conditional*: owned consumer hardware beats a T4-class instance per
  useful GPU-hour **only above ~7–15% sustained utilization** at residential
  power prices.
- **Depreciation, not electricity, dominates.** At $0.17/kWh a 250 W class
  costs ~$0.01–0.04/useful-hour in power but ~$0.026/hour in hardware
  amortization. Cheaper electricity alone does not fix a low-utilization fleet.
- **No willingness-to-pay data.** Credits are non-cash and priced 1:1 with
  useful units by construction (Sprint 28); customer price is unknown.

## 6. Next steps before any pricing decision

1. Measure a **real** AI workload (an adapter run) to replace the stub times.
2. Run a **multi-day, multi-machine** capture for true fleet utilization; add
   measured per-machine power (a metered plug or vendor telemetry).
3. Re-measure with a **CPU-only** contributor to fill the CPU baseline.
4. Only then choose a pricing/marketplace model (architecture §21).
