"""Payment provider adapter (Sprint 37).

A deliberately tiny seam: billing never talks to a vendor SDK directly, it
asks a provider to ``charge``/``refund`` and records the result. The prototype
ships a **simulated** provider only — it moves no real money, needs no
network, and requires no secrets (AGENTS.md non-goals: no real-money payouts).
A real provider (e.g. Stripe) can be added behind the same interface later
without touching pricing, ledgers, or compensation.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PaymentResult:
    """Outcome of a provider call (never contains card/bank details)."""

    ok: bool
    provider: str
    provider_ref: str
    amount_cents: int
    currency: str
    status: str  # succeeded | failed
    detail: str = ""


class PaymentProvider(Protocol):
    name: str

    def charge(
        self, *, customer_id: str, amount_cents: int, currency: str, reference: str
    ) -> PaymentResult: ...

    def refund(
        self, *, provider_ref: str, amount_cents: int, currency: str
    ) -> PaymentResult: ...


class SimulatedProvider:
    """Deterministic-in-shape stand-in: always succeeds, moves no money."""

    name = "simulated"

    def charge(
        self, *, customer_id: str, amount_cents: int, currency: str, reference: str
    ) -> PaymentResult:
        if amount_cents <= 0:
            return PaymentResult(
                ok=False, provider=self.name, provider_ref="", amount_cents=amount_cents,
                currency=currency, status="failed", detail="amount must be positive",
            )
        return PaymentResult(
            ok=True,
            provider=self.name,
            provider_ref=f"sim_{secrets.token_hex(12)}",
            amount_cents=amount_cents,
            currency=currency,
            status="succeeded",
            detail=f"simulated charge for {reference}",
        )

    def refund(
        self, *, provider_ref: str, amount_cents: int, currency: str
    ) -> PaymentResult:
        return PaymentResult(
            ok=True,
            provider=self.name,
            provider_ref=f"simr_{secrets.token_hex(12)}",
            amount_cents=amount_cents,
            currency=currency,
            status="succeeded",
            detail=f"simulated refund of {provider_ref}",
        )


_PROVIDERS: dict[str, PaymentProvider] = {SimulatedProvider.name: SimulatedProvider()}


def get_provider(name: str) -> PaymentProvider:
    """Resolve a configured provider, failing closed on an unknown name."""
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(f"unknown payment provider {name!r}")
    return provider
