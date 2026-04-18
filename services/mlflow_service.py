"""Institutional MLflow service for experiment tracking and registry."""

from __future__ import annotations

import os
import mlflow
from pathlib import Path
from typing import Optional, Any, Dict, List

from config import DATA_DIR

class MLflowService:
    """Wraps MLflow tracking and registry operations."""

    def __init__(self, experiment_name: str = "Backtest_Research"):
        self.data_path = Path(DATA_DIR)
        self.mlflow_db = self.data_path / "mlflow.db"
        self.artifact_path = self.data_path / "mlruns"
        
        # Ensure directories exist
        self.artifact_path.mkdir(parents=True, exist_ok=True)
        
        # Configure tracking URI
        tracking_uri = f"sqlite:///{self.mlflow_db}"
        mlflow.set_tracking_uri(tracking_uri)
        
        self.experiment_name = experiment_name
        mlflow.set_experiment(experiment_name)

    def start_run(self, run_name: Optional[str] = None) -> mlflow.ActiveRun:
        """Start a new MLflow run."""
        return mlflow.start_run(run_name=run_name)

    def log_backtest(self, result: Any, params: Dict[str, Any]):
        """Log a BacktestResult to MLflow.
        
        Args:
            result: engine.backtest_v2.BacktestResult
            params: dict of strategy parameters
        """
        with self.start_run(run_name=f"{result.strategy_name}_{result.metrics.get('annualized_return', 0):.2%}"):
            # 1. Log Parameters
            mlflow.log_params(params)
            mlflow.log_param("strategy_type", result.strategy_name)
            if result.data_hash:
                mlflow.log_param("data_hash", result.data_hash)
            
            # 2. Log Metrics
            m = result.metrics
            mlflow.log_metrics({
                "cum_ret_net": m.get("cumulative_return_net", 0.0),
                "ann_ret": m.get("annualized_return", 0.0),
                "sharpe": m.get("sharpe", 0.0),
                "max_dd": m.get("max_drawdown", 0.0),
                "volatility": m.get("volatility", 0.0),
                "alpha": m.get("alpha", 0.0),
                "beta": m.get("beta", 0.0),
                "var_95_corr_adj": m.get("var_95_corr_adj", 0.0),
                "avg_net_exposure": m.get("avg_net_exposure", 1.0),
                "n_trades": len(result.trades),
                "n_risk_violations": len(result.risk_violations)
            })
            
            # 3. Log Risk Violations as artifact if any
            if result.risk_violations:
                import json
                temp_v = self.data_path / "temp_violations.json"
                with open(temp_v, "w") as f:
                    json.dump(result.risk_violations, f, indent=2)
                mlflow.log_artifact(str(temp_v), "audit")
                os.remove(temp_v)

            # 4. Log History as artifact (CSV)
            import pandas as pd
            hist_df = pd.DataFrame(result.history)
            temp_h = self.data_path / "backtest_history.csv"
            hist_df.to_csv(temp_h, index=False)
            mlflow.log_artifact(str(temp_h), "backtest")
            os.remove(temp_h)

    def register_strategy(self, run_id: str, model_name: str):
        """Promote a successful strategy run to the Model Registry."""
        # In this project, 'models' are strategy configurations.
        # We can log the config as a 'model' artifact.
        # For simplicity, we just tag the run in the registry sense.
        result = mlflow.register_model(
            model_uri=f"runs:/{run_id}/strategy_config",
            name=model_name
        )
        return result

    def get_champion(self, model_name: str) -> Optional[mlflow.entities.model_registry.ModelVersion]:
        """Get the latest version tagged as Champion."""
        client = mlflow.tracking.MlflowClient()
        versions = client.get_latest_versions(model_name, stages=["Production"])
        return versions[0] if versions else None
