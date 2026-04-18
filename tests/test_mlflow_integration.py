"""Tests for MLflow tracking integration."""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from services.mlflow_service import MLflowService

@pytest.fixture
def mock_result():
    res = MagicMock()
    res.strategy_name = "test_strat"
    res.data_hash = "fake_hash"
    res.metrics = {
        "annualized_return": 0.15,
        "sharpe": 1.2,
        "max_drawdown": -0.05
    }
    res.trades = [{"ticker": "AAPL"}]
    res.risk_violations = []
    res.history = [{"date": "2024-01-01", "total_value": 100000}]
    return res

@patch("mlflow.set_tracking_uri")
@patch("mlflow.set_experiment")
@patch("mlflow.start_run")
@patch("mlflow.log_params")
@patch("mlflow.log_metrics")
@patch("mlflow.log_artifact")
def test_mlflow_log_backtest(mock_artifact, mock_metrics, mock_params, mock_start, mock_exp, mock_uri, mock_result, tmp_path):
    svc = MLflowService()
    svc.data_path = tmp_path
    
    params = {"threshold": 0.05}
    svc.log_backtest(mock_result, params)
    
    assert mock_params.called
    assert mock_metrics.called
    # Should log history CSV and potentially others
    assert mock_artifact.called
