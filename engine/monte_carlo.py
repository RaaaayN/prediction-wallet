"""Monte Carlo forward simulation for portfolio outcome distribution."""

from __future__ import annotations

import numpy as np


def run_monte_carlo(
    portfolio: dict,
    prices: dict,
    historical_returns: dict[str, list[float]],
    n_paths: int = 5000,
    horizon: int = 252,
) -> dict:
    """Simulate portfolio value distribution over a forward horizon.

    Args:
        portfolio: dict with a ``positions`` key mapping ticker → {shares: float},
                   and optionally a ``cash`` key.
        prices: current prices per ticker {ticker: float}.
        historical_returns: daily return history per ticker {ticker: [float, ...]}.
                            Tickers with fewer than 30 observations are silently dropped.
        n_paths: number of Monte Carlo paths (default 5 000).
        horizon: simulation horizon in trading days (default 252 = 1 year).

    Returns:
        dict with simulation summary statistics and a median path sample.
    """
    # ── 1. Current portfolio value ─────────────────────────────────────────────
    positions: dict[str, float | dict] = portfolio.get("positions", {})
    cash: float = float(portfolio.get("cash", 0.0))

    def _shares(position: float | dict) -> float:
        if isinstance(position, dict):
            return float(position.get("shares", position.get("quantity", 0.0)))
        return float(position)

    equity_value = 0.0
    for ticker, pos in positions.items():
        shares = _shares(pos)
        price = float(prices.get(ticker, 0.0))
        equity_value += shares * price

    total_value = equity_value + cash
    if total_value <= 0:
        total_value = max(cash, 1.0)  # fallback — avoid division by zero

    # ── 2. Eligible tickers and weights ───────────────────────────────────────
    eligible_tickers = [
        t for t in positions
        if t in historical_returns and len(historical_returns[t]) >= 30
    ]

    if not eligible_tickers:
        # No usable tickers — return a degenerate flat result
        flat = [total_value] * horizon
        return {
            "n_paths": n_paths,
            "horizon_days": horizon,
            "initial_value": total_value,
            "percentiles": {"p5": total_value, "p25": total_value, "p50": total_value,
                            "p75": total_value, "p95": total_value},
            "prob_loss": 0.0,
            "prob_drawdown_10pct": 0.0,
            "expected_sharpe": 0.0,
            "expected_max_dd": 0.0,
            "path_sample": flat,
        }

    # Weights proportional to current market value; cash is residual (not simulated)
    ticker_values = np.array([
        _shares(positions[t]) * float(prices.get(t, 0.0))
        for t in eligible_tickers
    ], dtype=np.float64)

    # Normalise against total portfolio value so weights sum ≤ 1.
    # The cash residual (1 - sum) earns zero return, consistent with simulation scope.
    weights = ticker_values / total_value  # shape (n_assets,)

    n_assets = len(eligible_tickers)

    # ── 3. Build returns matrix ────────────────────────────────────────────────
    # Align to the minimum available history length (at least 30 rows guaranteed above)
    min_len = min(len(historical_returns[t]) for t in eligible_tickers)
    returns_matrix = np.array(
        [historical_returns[t][-min_len:] for t in eligible_tickers],
        dtype=np.float64,
    )  # shape (n_assets, T)

    # ── 4. Mean and covariance in log-return space ────────────────────────────
    log_returns = np.log1p(returns_matrix)  # daily log-returns, shape (n_assets, T)
    mu = log_returns.mean(axis=1)           # shape (n_assets,)
    Sigma = np.cov(log_returns)             # shape (n_assets, n_assets)
    if n_assets == 1:
        Sigma = Sigma.reshape(1, 1)

    # ── 5. Cholesky decomposition with regularisation ─────────────────────────
    L = np.linalg.cholesky(Sigma + 1e-8 * np.eye(n_assets))  # shape (n_assets, n_assets)

    # ── 6. Simulate correlated log-returns — fully vectorised ─────────────────
    # Z: shape (n_paths, horizon, n_assets)
    rng = np.random.default_rng()
    Z = rng.standard_normal((n_paths, horizon, n_assets))

    # corr_Z[p, t, :] = mu + L @ Z[p, t, :]
    # Broadcast: Z @ L.T gives correlated innovations, then add mu
    corr_log_ret = Z @ L.T + mu[np.newaxis, np.newaxis, :]  # (n_paths, horizon, n_assets)

    # ── 7. Portfolio log-returns per day ──────────────────────────────────────
    # Weighted sum across assets: dot with weights → (n_paths, horizon)
    port_log_ret = corr_log_ret @ weights  # (n_paths, horizon)

    # ── 8. Cumulative portfolio value paths ───────────────────────────────────
    cum_log_ret = np.cumsum(port_log_ret, axis=1)          # (n_paths, horizon)
    # shape (n_paths, horizon)  — each row is a full value path
    value_paths = total_value * np.exp(cum_log_ret)

    # ── 9. Final values and basic statistics ──────────────────────────────────
    final_values = value_paths[:, -1]  # shape (n_paths,)

    pct = np.percentile(final_values, [5, 25, 50, 75, 95])
    prob_loss = float(np.mean(final_values < total_value))

    # ── 10. Max drawdown per path ─────────────────────────────────────────────
    # Prepend initial value as day-0 so drawdown is relative to the start
    full_paths = np.concatenate(
        [np.full((n_paths, 1), total_value), value_paths], axis=1
    )  # (n_paths, horizon+1)
    running_max = np.maximum.accumulate(full_paths, axis=1)  # (n_paths, horizon+1)
    drawdowns = (full_paths - running_max) / running_max      # negative or zero
    max_dd_per_path = drawdowns.min(axis=1)                   # most negative, shape (n_paths,)

    prob_dd_10 = float(np.mean(max_dd_per_path <= -0.10))
    expected_max_dd = float(np.mean(-max_dd_per_path))        # positive number
    max_dd_ci = np.percentile(-max_dd_per_path, [5, 50, 95])

    # ── 11. Expected Sharpe across paths ─────────────────────────────────────
    # Daily portfolio log-returns for each path; annualise
    path_mean_daily = port_log_ret.mean(axis=1)               # (n_paths,)
    path_std_daily = port_log_ret.std(axis=1)                 # (n_paths,)
    # Avoid division by zero for degenerate paths
    with np.errstate(divide="ignore", invalid="ignore"):
        path_sharpe = np.where(
            path_std_daily > 0,
            (path_mean_daily * 252) / (path_std_daily * np.sqrt(252)),
            0.0,
        )
    expected_sharpe = float(np.mean(path_sharpe))
    sharpe_ci = np.percentile(path_sharpe, [5, 50, 95])

    # ── 12. Median path sample ────────────────────────────────────────────────
    # Find the path whose final value is closest to the median final value
    median_final = float(pct[2])
    median_path_idx = int(np.argmin(np.abs(final_values - median_final)))
    path_sample: list[float] = value_paths[median_path_idx].tolist()

    return {
        "n_paths": n_paths,
        "horizon_days": horizon,
        "initial_value": float(total_value),
        "percentiles": {
            "p5":  float(pct[0]),
            "p25": float(pct[1]),
            "p50": float(pct[2]),
            "p75": float(pct[3]),
            "p95": float(pct[4]),
        },
        "prob_loss": prob_loss,
        "prob_drawdown_10pct": prob_dd_10,
        "expected_sharpe": expected_sharpe,
        "expected_max_dd": expected_max_dd,
        "confidence_intervals": {
            "final_value": {
                "p5": float(pct[0]),
                "p50": float(pct[2]),
                "p95": float(pct[4]),
            },
            "sharpe": {
                "p5": float(sharpe_ci[0]),
                "p50": float(sharpe_ci[1]),
                "p95": float(sharpe_ci[2]),
            },
            "max_drawdown": {
                "p5": float(max_dd_ci[0]),
                "p50": float(max_dd_ci[1]),
                "p95": float(max_dd_ci[2]),
            },
        },
        "path_sample": path_sample,
    }
