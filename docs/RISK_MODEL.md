# Institutional Risk Model

Prediction Wallet implements a quantitative risk framework covering multi-layer circuit breakers, return distribution analysis, factor attribution, and liquidity risk. Our framework aligns with institutional standards such as **Basel III** and the **Fundamental Review of the Trading Book (FRTB)**.

---

## 🛡️ Multi-Layer Circuit Breakers

The platform employs a deterministic hierarchy of risk controls that operate independently of the AI strategy layer.

### Layer 0: The Hard Kill Switch
A system-level circuit breaker that halts all execution if the portfolio suffers catastrophic loss.

```
drawdown = (peak_portfolio_value - current_portfolio_value) / peak_portfolio_value

if drawdown >= 0.10:
    kill_switch_active = True  → Layer 0 hard block → cycle aborted
```

| Drawdown | Risk Level | Action |
|----------|-----------|--------|
| < 7% | **OK** | Normal execution |
| 7–10% | **WARN** | Cycle proceeds, warning logged, no new leverage |
| ≥ 10% | **HALT** | Kill switch active, all execution blocked |

---

## 📊 Tail Risk Metrics (Basel III / FRTB Aligned)

We move beyond simple volatility to capture the "fat tails" of financial distributions.

### Value at Risk (VaR)
Estimates the maximum expected loss over a holding period (1-day or 10-day) at a given confidence level.
- **Parametric VaR**: Assumes normal distribution (μ - z_α × σ).
- **Historical VaR**: Uses empirical return distributions from the **Parquet Gold** data layer.

### Conditional VaR (CVaR / Expected Shortfall)
The institutional standard for tail risk, CVaR measures the average loss *given* that the VaR threshold has been breached.
```
CVaR = E[Loss | Loss > VaR_95]
```
CVaR is a coherent risk measure that captures sub-additivity, unlike standard VaR.

---

## 🔍 Factor & Risk Attribution

Understanding *where* risk comes from is as important as measuring its magnitude.

| Component | Metric | Interpretation |
|-----------|--------|----------------|
| **Beta (β)** | `Cov(R_p, R_m) / Var(R_m)` | Sensitivity to broader market movements (SPY/ACWI) |
| **Alpha (α)** | `R_p - [R_f + β(R_m - R_f)]` | Performance attributable to strategy/agent skill |
| **Sector Exposure** | `% Net Value per Sector` | Concentration risk in Technology, Finance, Energy, etc. |
| **Factor Loads** | `Fama-French 3-Factor` | Exposure to Size (SMB), Value (HML), and Momentum (WML) |

---

## 📏 Exposure & Concentration Limits

To prevent "hallucination-driven" over-concentration, the system enforces strict exposure bounds:

- **Gross Exposure**: `(Longs + |Shorts|) / Equity`. Max limit: 150%.
- **Net Exposure**: `(Longs - |Shorts|) / Equity`. Target range: -20% to +100%.
- **Single Ticker Cap**: No single asset can exceed 20% of the portfolio (adjustable by profile).
- **Sector Cap**: No single sector can exceed 55% of the portfolio.

---

## 💧 Liquidity Risk & Execution (TCA)

We model the cost of exiting positions in stressed markets.

- **Time-to-Liquidate**: Estimates days to exit a position assuming a max of 10% of Average Daily Volume (ADV).
- **Slippage (Market Impact)**: Uses a non-linear model based on volatility and order size relative to ADV.
- **Transaction Cost Analysis (TCA)**: Post-trade audit of executed price vs. arrival price (mid-price at decision time).

```
executed_price = arrival_price × (1 + base_slippage + size_impact)
```

---

## 🌩️ Macro Stress Testing

We apply calibrated historical shocks to the current holdings to estimate "Instantaneous Loss."

| Scenario | Equity | Bonds | Crypto | Volatility |
|----------|--------|-------|--------|------------|
| **2008 GFC** | -50% | +12% | N/A | 4.0× |
| **COVID Crash** | -34% | +8% | -50% | 3.0× |
| **2022 Rate Shock** | -20% | -15% | -65% | 2.0× |

Stress tests are executed every cycle and logged as part of the **MLflow** run metadata, ensuring strategy robustness across multiple regimes.
