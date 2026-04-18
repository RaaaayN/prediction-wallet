"""Institutional Governance and Compliance Monitoring Service."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

from db.repository import get_recent_risk_violations
from services.mlflow_service import MLflowService
from utils.time import utc_now_iso
from agents.models import GovernanceReport

class GovernanceService:
    """Consolidates audit trails, risk violations, and model lineage."""

    def __init__(self, profile_name: str = "balanced"):
        self.profile_name = profile_name
        self.mlflow_svc = MLflowService()

    def generate_governance_report(self) -> GovernanceReport:
        """Aggregate data for a comprehensive governance audit."""
        # 1. Fetch recent risk violations
        violations = get_recent_risk_violations(limit=20, profile_name=self.profile_name)
        
        # 2. Get Champion model info
        champion = self.mlflow_svc.get_champion("Rebalancing_Strategy")
        champion_name = f"Run {champion.run_id} (v{champion.version})" if champion else "None"
        
        # 3. Assess data lineage (simplified)
        # In a real system, we'd check DVC sync status
        lineage_status = "healthy"
        
        return GovernanceReport(
            timestamp=utc_now_iso(),
            total_cycles_scanned=100, # Placeholder for total historical cycles
            risk_violations_count=len(violations),
            recent_violations=violations,
            champion_strategy=champion_name,
            data_lineage_status=lineage_status
        )

    def export_report_to_json(self, path: str):
        """Export the governance report to a JSON file for archival."""
        report = self.generate_governance_report()
        with open(path, "w") as f:
            json.dump(report.model_dump(), f, indent=2)
        return path
