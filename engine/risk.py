"""Institutional risk computation functions — no I/O, no LLM."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from enum import Enum


class RiskLevel(str, Enum):
    """Tiered portfolio risk level."""
    OK   = "ok"
    WARN = "warn"
    HALT = "halt"


def get_risk_level(
    drawdown: float,
    warn_threshold: float = 0.07,
    halt_threshold: float = 0.10,
) -> RiskLevel:
    """Return the tiered risk level for a given drawdown.

    Args:
        drawdown: current drawdown (negative fraction, e.g. -0.08)
        warn_threshold: soft warning threshold (default 7%)
        halt_threshold: hard stop threshold (default 10%)

    Returns:
        RiskLevel.HALT if drawdown exceeds halt_threshold,
        RiskLevel.WARN if it exceeds warn_threshold,
        RiskLevel.OK otherwise.
    """
    if drawdown <= -halt_threshold:
        return RiskLevel.HALT
    if drawdown <= -warn_threshold:
        return RiskLevel.WARN
    return RiskLevel.OK


def compute_drawdown(current_value: float, peak_value: float) -> float:
    """Compute drawdown of current value from peak (negative number).

    Returns:
        Drawdown as a fraction, e.g. -0.15 means -15%
    """
    if peak_value <= 0:
        return 0.0
    return (current_value - peak_value) / peak_value


def check_kill_switch(drawdown: float, threshold: float) -> bool:
    """Return True if drawdown exceeds the threshold and trading should halt.

    Args:
        drawdown: current drawdown (negative fraction, e.g. -0.12)
        threshold: positive threshold value (e.g. 0.10 for 10%)

    Returns:
        True if abs(drawdown) > threshold (kill switch should activate)
    """
    return drawdown <= -threshold


def parametric_var(returns: pd.Series, confidence: float = 0.95, portfolio_value: float = 1.0) -> float:
    """Parametric (Gaussian) Value at Risk.

    Args:
        returns: daily return series
        confidence: confidence level (default 0.95)
        portfolio_value: total portfolio value in dollars

    Returns:
        VaR as a positive dollar loss (e.g. 1500.0 means "lose up to $1500 at 95% confidence")
    """
    if returns.empty or returns.std() == 0:
        return 0.0
    z = stats.norm.ppf(1 - confidence)
    var_pct = -(returns.mean() + z * returns.std())
    return float(var_pct * portfolio_value)


def conditional_var(returns: pd.Series, confidence: float = 0.95, portfolio_value: float = 1.0) -> float:
    """Conditional VaR (Expected Shortfall) — mean loss beyond VaR threshold.

    Args:
        returns: daily return series
        confidence: confidence level (default 0.95)
        portfolio_value: total portfolio value in dollars

    Returns:
        CVaR as a positive dollar loss
    """
    if returns.empty:
        return 0.0
    cutoff = returns.quantile(1 - confidence)
    tail = returns[returns <= cutoff]
    if tail.empty:
        return 0.0
    cvar_pct = -tail.mean()
    return float(cvar_pct * portfolio_value)


def historical_var(returns: pd.Series, confidence: float = 0.95, portfolio_value: float = 1.0) -> float:
    """Historical (empirical) Value at Risk — no distributional assumption.

    Args:
        returns: daily return series
        confidence: confidence level (default 0.95)
        portfolio_value: total portfolio value in dollars

    Returns:
        VaR as a positive dollar loss
    """
    if returns.empty:
        return 0.0
    cutoff = returns.quantile(1 - confidence)
    return float(max(0.0, -cutoff * portfolio_value))


def correlation_adjusted_var(
    weights: dict[str, float], 
    returns_df: pd.DataFrame, 
    confidence: float = 0.95, 
    portfolio_value: float = 1.0
) -> float:
    """Portfolio VaR accounting for correlations between assets.
    
    Uses annualized covariance matrix adjusted back to daily window.
    """
    if not weights or returns_df.empty:
        return 0.0
        
    tickers = sorted([t for t in weights.keys() if t in returns_df.columns])
    if not tickers:
        return 0.0
        
    # Align weights vector and returns matrix
    w = np.array([weights.get(t, 0.0) for t in tickers])
    r = returns_df[tickers]
    
    cov = r.cov() # Daily covariance matrix
    port_var = np.dot(w.T, np.dot(cov, w))
    port_vol = np.sqrt(port_var)
    
    z = stats.norm.ppf(1 - confidence)
    # Daily VaR = -(z * daily_portfolio_vol)
    var_pct = -(z * port_vol)
    return float(var_pct * portfolio_value)
