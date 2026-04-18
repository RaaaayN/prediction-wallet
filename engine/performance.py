"""Performance metrics — pure functions, no I/O, no LLM."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from config import RISK_FREE_RATE
import engine.risk as risk


def cumulative_return(history: list[dict]) -> float:
    """Compute cumulative return from portfolio history.

    Args:
        history: list of {"date": str, "total_value": float} dicts, ordered chronologically

    Returns:
        Cumulative return as a fraction (e.g. 0.15 = +15%)
    """
    if len(history) < 2:
        return 0.0
    start = history[0]["total_value"]
    end = history[-1]["total_value"]
    if start <= 0:
        return 0.0
    return (end - start) / start


def annualized_return(history: list[dict]) -> float:
    """Compute annualized return from portfolio history.

    Uses actual calendar days between first and last snapshot.

    Returns:
        Annualized return as a fraction
    """
    if len(history) < 2:
        return 0.0
    cum = cumulative_return(history)
    try:
        date_key = "date" if "date" in history[0] else "timestamp"
        start_date = pd.to_datetime(history[0][date_key])
        end_date = pd.to_datetime(history[-1][date_key])
        days = (end_date - start_date).days
    except Exception:
        days = len(history)  # fallback: assume 1 data point per day
    if days <= 0:
        return 0.0
    years = days / 365.25
    return (1.0 + cum) ** (1.0 / years) - 1.0


def rolling_volatility(returns: pd.Series, window: int = 30) -> pd.Series:
    """Rolling annualized volatility.

    Args:
        returns: daily return series
        window: rolling window in days

    Returns:
        Rolling annualized volatility series
    """
    return returns.rolling(window=window).std() * np.sqrt(252)


def sharpe_ratio(returns: pd.Series, rf: float = RISK_FREE_RATE) -> float:
    """Annualized Sharpe ratio.

    Args:
        returns: daily return series
        rf: annual risk-free rate (default: RISK_FREE_RATE from config)

    Returns:
        Sharpe ratio
    """
    if returns.empty or returns.std() == 0:
        return 0.0
    excess = returns.mean() * 252 - rf
    vol = returns.std() * np.sqrt(252)
    return float(excess / vol)


def max_drawdown(history: list[dict]) -> float:
    """Maximum drawdown from portfolio history.

    Returns:
        Max drawdown as a negative fraction (e.g. -0.20 = -20%)
    """
    if len(history) < 2:
        return 0.0
    values = pd.Series([h["total_value"] for h in history])
    peak = values.cummax()
    dd = (values - peak) / peak
    return float(dd.min())


def turnover(trades: list[dict], avg_portfolio_value: float) -> float:
    """Compute annualized turnover rate.

    Turnover = total trade volume / avg portfolio value.

    Args:
        trades: list of trade dicts with 'quantity', 'fill_price', 'timestamp' keys
        avg_portfolio_value: average portfolio value over the period

    Returns:
        Annualized turnover as a fraction
    """
    if not trades or avg_portfolio_value <= 0:
        return 0.0
    total_volume = sum(
        abs(t.get("quantity", 0)) * t.get("fill_price", t.get("market_price", 0))
        for t in trades
    )
    if not trades:
        return 0.0
    # Approximate annualization: assume period covered by trades
    try:
        dates = [pd.to_datetime(t["timestamp"]) for t in trades if "timestamp" in t]
        if len(dates) >= 2:
            days = (max(dates) - min(dates)).days
            years = max(days / 365.25, 1 / 365.25)
        else:
            years = 1.0
    except Exception:
        years = 1.0
    return (total_volume / avg_portfolio_value) / years


def transaction_costs_total(trades: list[dict]) -> float:
    """Sum of all transaction costs (slippage) from executed trades.

    Expects each trade dict to have 'quantity', 'market_price', 'fill_price'.

    Returns:
        Total slippage cost in dollars
    """
    total = 0.0
    for t in trades:
        qty = abs(t.get("quantity", 0.0))
        market = t.get("market_price", 0.0)
        fill = t.get("fill_price", market)
        total += qty * abs(fill - market)
    return total


def tracking_error(portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """Annualized tracking error vs benchmark.

    Args:
        portfolio_returns: daily portfolio return series
        benchmark_returns: daily benchmark return series

    Returns:
        Annualized tracking error as a fraction
    """
    aligned = portfolio_returns.align(benchmark_returns, join="inner")
    diff = aligned[0] - aligned[1]
    if diff.empty or diff.std() == 0:
        return 0.0
    return float(diff.std() * np.sqrt(252))


def hit_ratio(trades: list[dict]) -> float:
    """Fraction of trades that were successful.

    .. deprecated::
        Based on a simulator ``success`` boolean that is trivially True for all
        executed trades in simulation. Use :func:`avg_slippage_bps` instead for a
        meaningful execution quality metric. Kept for backward compatibility.

    Args:
        trades: list of trade dicts with a 'success' boolean key

    Returns:
        Hit ratio between 0 and 1
    """
    if not trades:
        return 0.0
    successes = sum(1 for t in trades if t.get("success", False))
    return successes / len(trades)


def avg_slippage_bps(trades: list[dict]) -> float:
    """Average execution slippage in basis points across all trades.

    Measures execution quality: how far fill prices deviated from market prices.
    Lower is better. Relevant for paper/live mode where fills reflect real market
    conditions rather than a fixed slippage model.

    Args:
        trades: list of trade dicts with 'market_price' and 'fill_price' keys

    Returns:
        Average slippage in basis points (e.g. 50.0 = 0.50%)
    """
    if not trades:
        return 0.0
    slippages = []
    for t in trades:
        market = t.get("market_price", 0.0)
        fill = t.get("fill_price", market)
        if market > 0:
            slippages.append(abs(fill - market) / market * 10_000)
    return float(np.mean(slippages)) if slippages else 0.0


def compute_liquidity_risk(
    position_size: float,
    avg_daily_volume: float,
    max_participation: float = 0.1,
) -> float:
    """Compute Time-to-Liquidate in days.

    Args:
        position_size: quantity of shares/units held
        avg_daily_volume: average daily traded volume (shares/units)
        max_participation: max percentage of daily volume to trade (default 10%)

    Returns:
        Estimated days to liquidate the full position.
    """
    if avg_daily_volume <= 0 or max_participation <= 0:
        return float("inf")
    return float(position_size / (avg_daily_volume * max_participation))


def compute_alpha_beta(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    rf_daily: float = 0.0,
) -> tuple[float, float]:
    """Compute annualized Jensen's Alpha and Beta via linear regression.

    Returns:
        tuple of (annualized_alpha, beta)
    """
    aligned = portfolio_returns.align(benchmark_returns, join="inner")
    y = aligned[0] - rf_daily
    x = aligned[1] - rf_daily
    if y.empty or x.empty or len(y) < 2:
        return 0.0, 1.0
    
    try:
        slope, intercept, _, _, _ = stats.linregress(x, y)
        # Annualize alpha: (1 + intercept)^252 - 1 (approximation) or intercept * 252
        ann_alpha = float(intercept * 252)
        beta = float(slope)
    except Exception:
        # Fallback for identical inputs or other regression failures
        ann_alpha = 0.0
        beta = 1.0
    
    return ann_alpha, beta


def parametric_var(returns: pd.Series, confidence: float = 0.95, portfolio_value: float = 1.0) -> float:
    """Parametric (Gaussian) Value at Risk."""
    return risk.parametric_var(returns, confidence, portfolio_value)


def conditional_var(returns: pd.Series, confidence: float = 0.95, portfolio_value: float = 1.0) -> float:
    """Conditional VaR (Expected Shortfall) — mean loss beyond VaR threshold."""
    return risk.conditional_var(returns, confidence, portfolio_value)


def historical_var(returns: pd.Series, confidence: float = 0.95, portfolio_value: float = 1.0) -> float:
    """Historical (empirical) Value at Risk — no distributional assumption."""
    return risk.historical_var(returns, confidence, portfolio_value)


def sortino_ratio(returns: pd.Series, rf: float = RISK_FREE_RATE, mar: float = 0.0) -> float:
    """Annualized Sortino ratio — uses only downside deviation.

    Args:
        returns: daily return series
        rf: annual risk-free rate
        mar: minimum acceptable return (daily, default 0.0)

    Returns:
        Sortino ratio (0.0 if no downside deviation)
    """
    if returns.empty:
        return 0.0
    downside = returns[returns < mar]
    if downside.empty or downside.std() == 0:
        return 0.0
    excess = returns.mean() * 252 - rf
    downside_vol = downside.std() * np.sqrt(252)
    return float(excess / downside_vol)


def calmar_ratio(history: list[dict], returns: pd.Series) -> float:
    """Calmar ratio — annualized return divided by absolute max drawdown.

    Args:
        history: portfolio snapshot history [{date, total_value}, ...]
        returns: daily return series (unused but kept for API consistency)

    Returns:
        Calmar ratio (0.0 if max drawdown is zero)
    """
    mdd = abs(max_drawdown(history))
    if mdd == 0:
        return 0.0
    ann_ret = annualized_return(history)
    return float(ann_ret / mdd)


def performance_report(
    history: list[dict],
    trades: list[dict],
    benchmark_history: list[dict] | None = None,
    exposures_history: list[dict] | None = None,
    returns_df: pd.DataFrame | None = None,
) -> dict:
    """Compute a comprehensive performance report.

    Args:
        history: portfolio snapshot history [{date, total_value}, ...]
        trades: executed trade list
        benchmark_history: optional benchmark history in same format
        exposures_history: optional list of exposure dicts over time
        returns_df: optional DataFrame of daily returns for correlation-adjusted VaR

    Returns:
        Dict with all performance metrics, both gross and net of costs
    """
    if not history:
        return {}

    values = pd.Series([h["total_value"] for h in history])
    daily_returns = values.pct_change().dropna()

    costs = transaction_costs_total(trades)
    avg_value = float(values.mean()) if len(values) > 0 else 1.0

    cum_ret_gross = cumulative_return(history)
    # Net: subtract total costs from final value
    net_final = history[-1]["total_value"] - costs
    net_start = history[0]["total_value"]
    cum_ret_net = (net_final - net_start) / net_start if net_start > 0 else 0.0

    report = {
        "cumulative_return_gross": cum_ret_gross,
        "cumulative_return_net": cum_ret_net,
        "annualized_return": annualized_return(history),
        "volatility": float(daily_returns.std() * np.sqrt(252)) if not daily_returns.empty else 0.0,
        "sharpe": sharpe_ratio(daily_returns),
        "sortino": sortino_ratio(daily_returns),
        "calmar": calmar_ratio(history, daily_returns),
        "max_drawdown": max_drawdown(history),
        "var_95_parametric": parametric_var(daily_returns, 0.95, avg_value),
        "var_99_parametric": parametric_var(daily_returns, 0.99, avg_value),
        "var_95_historical": historical_var(daily_returns, 0.95, avg_value),
        "var_99_historical": historical_var(daily_returns, 0.99, avg_value),
        "cvar_95": conditional_var(daily_returns, 0.95, avg_value),
        "cvar_99": conditional_var(daily_returns, 0.99, avg_value),
        "turnover": turnover(trades, avg_value),
        "transaction_costs": costs,
        "avg_slippage_bps": avg_slippage_bps(trades),
    }

    if exposures_history:
        exp_df = pd.DataFrame(exposures_history)
        if not exp_df.empty:
            report["avg_gross_exposure"] = float(exp_df["gross_exposure"].mean()) if "gross_exposure" in exp_df.columns else 1.0
            report["avg_net_exposure"] = float(exp_df["net_exposure"].mean()) if "net_exposure" in exp_df.columns else 1.0
            report["max_leverage"] = float(exp_df["leverage_used"].max()) if "leverage_used" in exp_df.columns else 1.0
            
            # Correlation-adjusted VaR (using latest weights)
            if returns_df is not None and not returns_df.empty:
                last_exp = exposures_history[-1]
                weights = last_exp.get("single_name_concentration", {})
                report["var_95_corr_adj"] = risk.correlation_adjusted_var(weights, returns_df, 0.95, avg_value)
    else:
        report["avg_gross_exposure"] = 1.0
        report["avg_net_exposure"] = 1.0
        report["max_leverage"] = 1.0

    if benchmark_history:
        bm_values = pd.Series([h["total_value"] for h in benchmark_history])
        bm_returns = bm_values.pct_change().dropna()
        report["tracking_error"] = tracking_error(daily_returns, bm_returns)
        report["benchmark_cumulative_return"] = cumulative_return(benchmark_history)
        
        # Add Alpha and Beta
        alpha, beta = compute_alpha_beta(daily_returns, bm_returns)
        report["alpha"] = alpha
        report["beta"] = beta
    else:
        report["tracking_error"] = None
        report["benchmark_cumulative_return"] = None
        report["alpha"] = 0.0
        report["beta"] = 1.0

    return report


def rolling_correlation(
    returns_df: pd.DataFrame,
    window: int = 30,
) -> pd.DataFrame:
    """Compute correlation matrix over the last `window` periods.

    Args:
        returns_df: DataFrame with columns = tickers, rows = daily returns
        window: number of most-recent periods to use (default 30 days)

    Returns:
        Correlation matrix as a DataFrame. Returns an empty DataFrame if
        input has fewer than 2 rows or is empty.
    """
    if returns_df.empty or len(returns_df) < 2:
        return pd.DataFrame()
    return returns_df.iloc[-window:].corr()


def avg_pairwise_correlation(corr_matrix: pd.DataFrame) -> float:
    """Mean of off-diagonal elements of a correlation matrix.

    Measures average pairwise correlation across assets.
    Lower values indicate better diversification.

    Args:
        corr_matrix: square correlation matrix (output of rolling_correlation or pd.DataFrame.corr)

    Returns:
        Average off-diagonal correlation. Returns 0.0 for matrices with fewer than 2 assets.
    """
    n = len(corr_matrix)
    if n <= 1:
        return 0.0
    mask = ~np.eye(n, dtype=bool)
    return float(corr_matrix.values[mask].mean())
