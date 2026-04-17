# Risk Model

Prediction Wallet implements a quantitative risk framework covering drawdown controls, return distribution analysis, and crisis stress testing.

## Kill Switch

The kill switch is a hard, deterministic circuit breaker. It runs before any LLM decision is validated.

```
drawdown = (peak_value - current_value) / peak_value

if drawdown >= 0.10:
    kill_switch_active = True  → Layer 0 hard block → cycle aborted
```

Peak value is the highest `total_value` recorded across all portfolio snapshots. The kill switch cannot be overridden by the AI agent or by profile configuration — it is a system-level constraint.

**Threshold levels:**

| Drawdown | Risk Level | Action |
|----------|-----------|--------|
| < 7% | OK | Normal execution |
| 7–10% | WARN | Cycle proceeds, warning logged |
| ≥ 10% | HALT | Kill switch active, cycle aborted |

## Value at Risk (VaR)

VaR estimates the maximum expected loss over a holding period at a given confidence level.

### Parametric VaR

Assumes normally distributed returns:

```
VaR_parametric = μ - z_α × σ

where:
  μ = mean daily return
  σ = standard deviation of daily returns
  z_α = 1.645 for 95% confidence, 2.326 for 99%
```

### Historical VaR

Uses the empirical return distribution — no normality assumption:

```
VaR_historical = percentile(returns, 1 - confidence_level)
```

Historical VaR captures fat tails and asymmetry that parametric VaR misses, particularly relevant for crypto-heavy portfolios.

## Conditional VaR (CVaR / Expected Shortfall)

CVaR answers: *given that we exceed VaR, how bad is it on average?*

```
CVaR = mean(returns[returns < VaR_threshold])
```

CVaR is a coherent risk measure (unlike VaR) and is the standard in Basel III / FRTB regulatory frameworks. Prediction Wallet reports CVaR at 95% confidence alongside VaR.

## Return-Based Metrics

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Sharpe Ratio** | `(R_p - R_f) / σ_p` | Excess return per unit of total risk |
| **Sortino Ratio** | `(R_p - R_f) / σ_downside` | Excess return per unit of downside risk only |
| **Calmar Ratio** | `R_p / max_drawdown` | Return per unit of max drawdown risk |
| **Max Drawdown** | `max((peak - trough) / peak)` | Worst peak-to-trough loss |

All ratios use annualized returns. Risk-free rate default: 0% (configurable).

Sortino is particularly useful for crypto-heavy profiles where upside volatility is large but not a risk — only downside volatility matters.

## Stress Testing

Four calibrated crisis scenarios are applied to the current portfolio to estimate loss under extreme conditions:

| Scenario | Equity Shock | Bond Shock | Crypto Shock | Vol Multiplier |
|----------|-------------|-----------|--------------|----------------|
| **COVID-19 Crash** (Mar 2020) | -34% | +8% | -50% | 3× |
| **2008 GFC** | -50% | +12% | N/A | 4× |
| **Rate Shock** (2022) | -20% | -15% | -65% | 2× |
| **Tech Selloff** | -40% | +5% | -35% | 2.5× |

Each scenario returns:
- Estimated portfolio P&L in dollars
- Estimated portfolio P&L as a percentage
- Whether the scenario would trigger the kill switch (drawdown ≥ 10%)

Stress test results are surfaced in the UI (Stress Test tab) and included in PDF reports.

## Slippage Model

Trade execution uses a volume-adjusted slippage model:

```
slippage_rate = base_rate × vol_factor + size_factor

where:
  base_rate   = profile-level parameter (default: 0.001 = 10bps)
  vol_factor  = 1.0 + (asset_volatility / 0.20)   [normalized to 20% annual vol]
  size_factor = +0.0001 per $10,000 notional       [market impact]

executed_price = market_price × (1 + slippage_rate)  [buys]
executed_price = market_price × (1 - slippage_rate)  [sells]
```

Every execution stores `slippage_pct` in the `executions` table, enabling post-trade analysis of execution quality.

## Correlation Analysis

The correlation matrix across all portfolio assets is computed from historical daily returns. The UI renders this as a heatmap (Correlation tab).

High off-diagonal correlations (> 0.85) signal concentration risk — the portfolio behaves as fewer independent assets than it appears. This is particularly important during stress periods when correlations tend to converge toward 1.

## Portfolio Drift Monitoring

Target allocation drift is computed per asset:

```
drift = (current_weight - target_weight) / target_weight
```

Rebalancing triggers when drift exceeds the profile threshold band. Per-asset bands (`per_asset_threshold` in `profiles/*.yaml`) allow tighter control on volatile assets (e.g., crypto) while allowing wider bands on liquid equities.
