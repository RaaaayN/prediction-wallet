"""Health and Readiness service for platform monitoring."""

from __future__ import annotations
import os
import shutil
import sqlite3
from typing import Dict, Any
from db.connection import get_connection
from db.repository import get_market_data_status
from config import MARKET_DB

class HealthService:
    """Checks the health of various platform components."""

    def check_database(self) -> Dict[str, Any]:
        """Verify database connectivity and basic integrity."""
        try:
            with get_connection() as conn:
                # Check if we can reach a core table
                conn.execute("SELECT 1 FROM instruments LIMIT 1").fetchone()
                return {"status": "up", "type": "sqlite" if "sqlite" in str(MARKET_DB) else "postgres"}
        except Exception as e:
            return {"status": "down", "error": str(e)}

    def check_market_data(self) -> Dict[str, Any]:
        """Verify local market-data freshness without calling external providers."""
        try:
            rows = get_market_data_status()
            return {"status": "up", "provider": "local-cache", "rows": len(rows)}
        except Exception as e:
            return {"status": "down", "error": str(e)}

    def check_disk_space(self) -> Dict[str, Any]:
        """Ensure there is enough disk space for logs and DB."""
        total, used, free = shutil.disk_usage("/")
        free_gb = free // (2**30)
        return {
            "status": "up" if free_gb > 1 else "warning",
            "free_gb": free_gb,
            "used_pct": round(used / total * 100, 1)
        }

    def get_full_health(self) -> Dict[str, Any]:
        """Consolidate all health checks."""
        db = self.check_database()
        market = self.check_market_data()
        disk = self.check_disk_space()
        
        overall = "up"
        if db["status"] == "down" or market["status"] == "down":
            overall = "down"
        elif disk["status"] == "warning":
            overall = "degraded"
            
        return {
            "status": overall,
            "checks": {
                "database": db,
                "market_data": market,
                "disk": disk
            }
        }
