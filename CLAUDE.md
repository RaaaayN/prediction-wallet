# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Prediction Wallet is an **autonomous AI portfolio rebalancing agent** powered by LangGraph + Claude. It monitors a 9-asset portfolio (equities, bonds, crypto), detects drift from target allocations, executes simulated trades with slippage, and generates PDF audit reports.

## Commands

### Setup
```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env     # then set ANTHROPIC_API_KEY
```

### Run
```bash
# One agent cycle (threshold strategy, default)
python main.py

# Calendar strategy
python main.py --strategy calendar

# Fast-forward 30 days
python main.py --simulate-days 30

# Generate PDF report only
python main.py --report

# Streamlit dashboard
streamlit run dashboard/app.py

# Tests
pytest tests/ -v
```

## Architecture

### Agent Flow (LangGraph)
```
[observe] → fetch prices + compute metrics + strategy signal
[analyze] → Claude: market summary + anomaly detection
[decide]  → Claude tool-calling loop: get_portfolio_state → get_market_data → execute_trade
[execute] → post-trade validation + kill switch check
    ├─ kill switch? → [alert] → END
    └─ normal      → [audit] → PDF report → END
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `config.py` | Target allocations, thresholds, API key, paths |
| `agent/graph.py` | LangGraph state machine |
| `agent/nodes.py` | Node implementations (observe/analyze/decide/execute/audit) |
| `agent/tools.py` | Claude tools: get_portfolio_state, get_market_data, execute_trade, generate_report |
| `agent/state.py` | AgentState TypedDict |
| `agent/prompts.py` | System prompt + analysis/decision templates |
| `strategies/threshold.py` | Drift-based rebalancing (±5% default) |
| `strategies/calendar.py` | Time-based rebalancing (weekly/monthly) |
| `market/fetcher.py` | yfinance → SQLite (market.db) |
| `market/metrics.py` | Returns, volatility, Sharpe, drawdown |
| `execution/simulator.py` | Simulated order execution with slippage |
| `execution/kill_switch.py` | 10% drawdown → emergency stop |
| `reporting/pdf_report.py` | reportlab PDF generation |
| `dashboard/app.py` | Streamlit dashboard |

### Data Paths

| Path | Contents |
|------|---------|
| `data/market.db` | SQLite: OHLCV + technical indicators per ticker |
| `data/portfolio.json` | Portfolio state (positions, cash, history) |
| `data/trades.log` | JSONL trade log + kill switch alerts |
| `data/reports/` | Generated PDF reports (`report_<cycle_id>.pdf`) |

### Portfolio Configuration (`config.py`)
- **Target:** AAPL 12%, MSFT 12%, GOOGL 9%, AMZN 9%, NVDA 8%, TLT 15%, BND 15%, BTC-USD 12%, ETH-USD 8%
- **Initial capital:** $100,000
- **Drift threshold:** 5% → triggers ThresholdStrategy
- **Kill switch:** 10% drawdown from peak → halts all trading
- **Slippage:** 0.1% equities, 0.5% crypto

### Claude Tools
The agent calls these tools in its decision loop:
1. `get_portfolio_state` — positions, weights, cash, drawdown
2. `get_market_data(tickers)` — price, vol30d, YTD, Sharpe per ticker
3. `execute_trade(action, ticker, quantity, reason)` — simulated fill with slippage
4. `generate_report(cycle_id)` — triggers PDF generation, returns path
