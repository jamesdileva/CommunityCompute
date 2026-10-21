"""Operator billing endpoints (Sprint 37).

Unauthenticated in the prototype, matching the existing operator customer
routes. These are read-only network/pricing views plus the prepaid account
roll-up; customers use `/api/v1/billing` for their own balance.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.billing import AccountBalance, NetworkRevenue, PricingOut
from app.services import billing

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/pricing", response_model=PricingOut)
def get_pricing() -> dict:
    """The active per-unit rate card and network fee percent."""
    return {
        "currency": billing.currency(),
        "network_fee_percent": billing.network_fee_percent(),
        "rate_card": billing.rate_card(),
    }


@router.get("/network", response_model=NetworkRevenue)
def get_network_revenue(db: Session = Depends(get_db)) -> dict:
    """Charged vs contributor vs network, plus per-workload charges."""
    return billing.network_summary(db)


@router.get("/accounts", response_model=list[AccountBalance])
def list_accounts(db: Session = Depends(get_db)) -> list[dict]:
    """Every customer's prepaid balance (operator visibility)."""
    return billing.account_balances(db)
