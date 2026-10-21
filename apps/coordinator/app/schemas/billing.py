"""Billing API schemas (Sprint 37)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TopupRequest(BaseModel):
    amount_cents: int = Field(gt=0)


class TopupResult(BaseModel):
    payment_id: str
    provider: str
    provider_ref: str
    amount_cents: int
    currency: str
    status: str
    balance_cents: int


class JobChargeOut(BaseModel):
    job_id: str
    workload_type: str
    units: int
    unit_price_cents: int
    amount_cents: int
    network_fee_percent: int
    currency: str
    created_at: str | None = None


class BillingSummary(BaseModel):
    customer_id: str
    currency: str
    balance_cents: int
    lifetime_topup_cents: int
    lifetime_charged_cents: int
    network_fee_percent: int
    rate_card: dict[str, int]
    charges: list[JobChargeOut]


class PricingOut(BaseModel):
    currency: str
    network_fee_percent: int
    rate_card: dict[str, int]


class NetworkRevenue(BaseModel):
    currency: str
    network_fee_percent: int
    topup_cents: int
    charged_cents: int
    contributor_cents: int
    network_cents: int
    unallocated_cents: int
    jobs: int
    by_workload: dict[str, int]


class AccountBalance(BaseModel):
    customer_id: str
    name: str
    status: str
    balance_cents: int
    currency: str


class EarningsEntry(BaseModel):
    job_id: str
    work_unit_id: str | None = None
    amount_cents: int
    voided: bool
    created_at: str | None = None


class WorkerEarnings(BaseModel):
    worker_id: str
    currency: str
    balance_cents: int
    entries: list[EarningsEntry]
