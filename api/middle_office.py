"""Middle Office API for reconciliation and TCA."""

from __future__ import annotations
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from api.auth import Role, User, requires_role
from services.middle_office_service import MiddleOfficeService, ReconciliationBreak, TCAReport

router = APIRouter(prefix="/api/middle-office", tags=["Middle Office"])

@router.get("/reconcile", response_model=List[ReconciliationBreak])
async def get_reconciliation(_: User = Depends(requires_role([Role.TRADER, Role.ADMIN]))):
    """Run reconciliation between legacy portfolio and Trading Core Ledger."""
    svc = MiddleOfficeService()
    return svc.reconcile_holdings()

@router.post("/sync", status_code=200)
async def post_sync(_: User = Depends(requires_role([Role.ADMIN]))):
    """Force sync legacy state from the Ledger source of truth."""
    svc = MiddleOfficeService()
    return svc.sync_legacy_to_ledger()

@router.get("/tca/{cycle_id}", response_model=TCAReport)
async def get_tca(cycle_id: str, _: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN]))):
    """Get Transaction Cost Analysis for a specific cycle."""
    svc = MiddleOfficeService()
    report = svc.generate_tca_report(cycle_id)
    if not report.total_trades and cycle_id != "manual":
        raise HTTPException(status_code=404, detail=f"No executions found for cycle {cycle_id}")
    return report
