"""Rolling market regime detection based on volatility percentiles."""

from __future__ import annotations

import numpy as np
import pandas as pd


def detect_regime(returns_df: pd.DataFrame) -> dict:
    """Classify the current market regime from a daily-returns DataFrame.

    Args:
        returns_df: DataFrame of daily returns, columns = tickers, rows = dates.
                    Any NaN values are forward-filled then dropped per row.

    Returns:
        dict with regime label, volatility metrics, and a soft-block recommendation.
    """
    if returns_df.empty or len(returns_df) < 30:
        return {
            "regime": "unknown",
            "error": "Insufficient data",
            "vol_30d": 0.0,
            "vol_90d": 0.0,
            "vol_ratio": 1.0,
            "return_30d": 0.0,
            "description": "Not enough return history to detect regime.",
            "soft_block_recommended": False,
        }

    clean_returns = returns_df.ffill().dropna(how="any")
    if clean_returns.empty or len(clean_returns) < 30:
        return {
            "regime": "unknown",
            "error": "Insufficient data",
            "vol_30d": 0.0,
            "vol_90d": 0.0,
            "vol_percentile": 0.0,
            "return_30d": 0.0,
            "description": "Not enough return history to detect regime.",
            "soft_block_recommended": False,
        }

    # Equal-weight portfolio returns across all tickers
    port_returns: pd.Series = clean_returns.mean(axis=1)

    # Rolling annualised volatility
    vol_30d_series = port_returns.rolling(window=30).std() * np.sqrt(252)
    vol_90d_series = port_returns.rolling(window=90).std() * np.sqrt(252)

    vol_30d = float(vol_30d_series.iloc[-1]) if not pd.isna(vol_30d_series.iloc[-1]) else 0.0
    vol_90d = float(vol_90d_series.iloc[-1]) if not pd.isna(vol_90d_series.iloc[-1]) else vol_30d

    # Avoid division by zero
    hist_window = vol_30d_series.dropna()
    vol_percentile = float((hist_window <= vol_30d).mean()) if not hist_window.empty else 0.5
    vol_ratio = (vol_30d / vol_90d) if vol_90d > 0 else 1.0

    # 30-day cumulative return (sum of last 30 daily returns — approximation)
    return_30d = float(port_returns.iloc[-30:].sum()) if len(port_returns) >= 30 else 0.0

    # ── Classification (evaluated in priority order) ───────────────────────────
    if vol_percentile >= 0.9:
        regime = "risk_off"
        description = (
            f"Volatility at the {vol_percentile:.0%} percentile — risk-off conditions."
        )
    elif vol_percentile >= 0.7 and return_30d < -0.03:
        regime = "bear"
        description = (
            f"Elevated volatility ({vol_percentile:.0%} percentile) with negative momentum "
            f"({return_30d:.1%} 30d return) — bear conditions."
        )
    elif vol_percentile <= 0.3 and return_30d > 0.03:
        regime = "bull"
        description = (
            f"Suppressed volatility ({vol_percentile:.0%} percentile) with positive momentum "
            f"({return_30d:.1%} 30d return) — bull conditions."
        )
    else:
        regime = "normal"
        description = (
            f"Volatility percentile {vol_percentile:.0%}, 30d return {return_30d:.1%} — normal conditions."
        )

    soft_block_recommended = regime in ("risk_off", "bear")

    return {
        "regime": regime,
        "vol_30d": round(vol_30d, 6),
        "vol_90d": round(vol_90d, 6),
        "vol_ratio": round(vol_ratio, 4),
        "vol_percentile": round(vol_percentile, 4),
        "return_30d": round(return_30d, 6),
        "description": description,
        "soft_block_recommended": soft_block_recommended,
    }


def get_current_regime(tickers: list[str], days: int = 180) -> dict:
    """Fetch historical data from MarketService and classify the current regime.

    Args:
        tickers: list of portfolio tickers.
        days: number of calendar days of history to load (default 180).

    Returns:
        Result of :func:`detect_regime`, or an error dict if data is insufficient.
    """
    from services.market_service import MarketService

    svc = MarketService()
    price_series: dict[str, pd.Series] = {}

    for ticker in tickers:
        try:
            hist = svc.get_historical(ticker, days=days)
            if not hist.empty and "Close" in hist.columns:
                price_series[ticker] = hist["Close"]
        except Exception:
            # Silently drop tickers that fail to load
            continue

    if not price_series:
        return {
            "regime": "unknown",
            "error": "No market data available for any ticker.",
            "vol_30d": 0.0,
            "vol_90d": 0.0,
            "vol_ratio": 1.0,
            "return_30d": 0.0,
            "description": "No market data could be loaded.",
            "soft_block_recommended": False,
        }

    prices_df = pd.DataFrame(price_series).dropna(how="all")
    returns_df = prices_df.pct_change().dropna(how="all")

    if len(returns_df) < 60:
        return {"regime": "unknown", "error": "Insufficient data"}

    return detect_regime(returns_df)
