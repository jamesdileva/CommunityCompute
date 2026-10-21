# Pricing and paid compute (Sprint 37)

This document describes the **paid-compute experiment**: a controlled
customer can prepay for a supported workload and the system calculates the
contributor / network split of every verified work unit.

> **No real money moves.** The only payment provider in the prototype is
> `simulated`. It records a charge, moves no funds, needs no network, and
> stores no card or bank data. Payouts are a non-goal for the prototype
> (`AGENTS.md` §7) and are not implemented.

## The flow

```text
operator mints a customer key
        -> customer POST /api/v1/billing/topup        (prepaid balance += amount)
        -> customer POST /api/v1/jobs                 (balance -= units x unit price)
        -> worker completes a verified original unit  (contributor += 80%, network += 20%)
```

* The job charge is **upfront** and atomic with job creation. A customer with
  a short balance gets `402` and no job, units, or ledger rows are written.
* Work units that fail, are rejected, or are **duplicate verification** units
  earn no compensation.
* If a duplicate disagrees with an original, the original is overturned: its
  **contributor** share is voided (history is kept), while the network keeps
  the fee for the failed attempt.

## Rate card

Prices are integer cents per **verified work unit** and are frozen onto the
job at submit time (later rate changes never re-price accepted work).

| Workload         | Cents / unit |
| ---------------- | -----------: |
| `hello_compute`  |            5 |
| `stats_range`    |            3 |
| `embeddings`     |           10 |
| `image_generate` |           25 |

The default network fee is **20%**, so a 5-cent unit pays the contributor
**4 cents** and the network **1 cent**. Both shares always sum to the unit
price (integer, half-up rounding).

## Configuration

| Setting                        | Default   | Meaning                               |
| ------------------------------ | --------- | ------------------------------------- |
| `BILLING_CURRENCY`             | `USD`     | Display/accounting currency           |
| `PAYMENT_PROVIDER`             | `simulated` | Provider adapter name               |
| `PRICING_NETWORK_FEE_PERCENT`  | `20`      | Network share of each unit (0–100)    |
| `PRICING_RATE_CARD`            | *(empty)* | JSON object merged over the defaults  |
| `BILLING_MIN_TOPUP_CENTS`      | `100`     | Smallest accepted top-up              |
| `BILLING_MAX_TOPUP_CENTS`      | `100000`  | Largest accepted top-up               |

Example override:

```text
PRICING_RATE_CARD={"hello_compute": 10, "image_generate": 50}
PRICING_NETWORK_FEE_PERCENT=25
```

An invalid rate card fails closed (pricing calls raise rather than silently
defaulting).

## API

### Customer (bearer key)

| Method | Path                     | Purpose                                  |
| ------ | ------------------------ | ---------------------------------------- |
| `GET`  | `/api/v1/billing`        | Balance, lifetime totals, rate card, charges |
| `POST` | `/api/v1/billing/topup`  | `{"amount_cents": 500}` → provider charge + credit |

`POST /api/v1/jobs` returns `402` with `need_cents` / `balance_cents` when the
prepaid balance is too low.

### Operator (unauthenticated in the prototype)

| Method | Path                  | Purpose                                  |
| ------ | --------------------- | ---------------------------------------- |
| `GET`  | `/billing/pricing`    | Active rate card + fee percent           |
| `GET`  | `/billing/network`    | Charged vs contributor vs network totals |
| `GET`  | `/billing/accounts`   | Every customer's prepaid balance         |

### Contributor

`GET /workers/{worker_id}/earnings` returns the worker's compensation entries
and non-voided balance. The dashboard "My node" tab shows the same total.

## Exit proof

`scripts/paid_compute_demo.py` drives the whole loop against a live
coordinator: mint customer → top-up → submit prepaid job → real worker
executes → assert `charged == contributor + network`, both shares positive,
and `balance == top-up - charged`. Exit code 0 is the proof.

## Explicit non-goals (prototype)

* Real payment processing, refunds, or payouts.
* Contributor cash-out or tax reporting.
* Dynamic/auction pricing, per-customer discounts, invoicing.
* Public self-serve signup (enrollment stays operator-controlled).
