"""Middle Office API for reconciliation and TCA."""

from __future__ import annotations
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from api.auth import Role, User, requires_role
from services.middle_office_service import MiddleOfficeService, ReconciliationBreak, TCAReport
from services.back_office_service import BackOfficeService

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

@router.get("/reconcile/history")
async def get_reconciliation_history(_: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN]))):
    """View history of reconciliation runs."""
    from db.repository import get_connection, q
    with get_connection() as conn:
        rows = conn.execute(q("SELECT * FROM reconciliation_runs ORDER BY timestamp DESC LIMIT 50")).fetchall()
    return [dict(r) for r in rows]

@router.get("/reconcile/{run_id}/breaks", response_model=List[ReconciliationBreak])
async def get_reconciliation_run_breaks(run_id: str, _: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN]))):
    """View breaks for a specific reconciliation run."""
    from db.repository import get_connection, q
    with get_connection() as conn:
        rows = conn.execute(q("SELECT * FROM reconciliation_breaks WHERE run_id = ?"), (run_id,)).fetchall()
    return [dict(r) for r in rows]

@router.get("/tca", response_model=List[TCAReport])
async def list_tca_reports(_: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN]))):
    """List all persisted TCA reports."""
    from db.repository import get_connection, q
    import json
    with get_connection() as conn:
        rows = conn.execute(q("SELECT * FROM tca_reports ORDER BY timestamp DESC")).fetchall()
    
    payload = []
    for r in rows:
        d = dict(r)
        d["trade_details"] = json.loads(d.pop("details_json"))
        payload.append(TCAReport(**d))
    return payload

@router.get("/tca/{cycle_id}", response_model=TCAReport)
async def get_tca(cycle_id: str, _: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN]))):
    """Get Transaction Cost Analysis for a specific cycle."""
    svc = MiddleOfficeService()
    report = svc.generate_tca_report(cycle_id)
    if not report.total_trades and cycle_id != "manual":
        raise HTTPException(status_code=404, detail=f"No executions found for cycle {cycle_id}")
    return report

# --- Back Office & Regulatory Reporting ---

@router.get("/nav/history")
async def get_nav_history_api(_: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN]))):
    """View history of Net Asset Value (NAV) runs."""
    from db.repository import get_nav_history
    return get_nav_history()

@router.post("/nav/calculate")
async def run_nav_calculation(_: User = Depends(requires_role([Role.ADMIN]))):
    """Trigger a new NAV calculation based on current ledger and prices."""
    svc = BackOfficeService()
    return svc.calculate_daily_nav()

@router.get("/reports/mifir/{cycle_id}")
async def get_mifir_report(cycle_id: str, _: User = Depends(requires_role([Role.ADMIN, Role.TRADER]))):
    """Generate a regulatory MiFIR-compliant transaction record for a cycle."""
    svc = BackOfficeService()
    export = svc.get_regulatory_mifir_export(cycle_id)
    if not export:
        raise HTTPException(status_code=404, detail=f"No transactions found for cycle {cycle_id}")
    return export
