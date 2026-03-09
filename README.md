# Prediction Wallet — Autonomous Portfolio Rebalancing Agent

An AI-powered portfolio manager that autonomously monitors drift, rebalances allocations, simulates trades with slippage, and generates PDF audit reports — all driven by a LangGraph agent backed by Claude.

## Stack

- **AI Agent:** LangGraph + Anthropic Claude (claude-sonnet-4-6)
- **Data:** yfinance → SQLite (`data/market.db`)
- **Strategies:** Threshold (drift-based) or Calendar (weekly/monthly)
- **Execution:** Simulated trades with realistic slippage
- **Reporting:** reportlab PDF audit reports
- **Dashboard:** Streamlit

## Directory Structure

```
prediction-wallet-1/
├── agent/              # LangGraph agent (state, graph, nodes, tools, prompts)
├── strategies/         # Threshold + Calendar rebalancing strategies
├── market/             # yfinance data fetching + metrics
├── execution/          # Trade simulator + kill switch
├── reporting/          # PDF report generation
├── dashboard/          # Streamlit app
├── tests/              # pytest test suite
├── data/
│   ├── market.db       # SQLite: price history + indicators
│   ├── portfolio.json  # Portfolio state
│   ├── trades.log      # JSONL trade log
│   └── reports/        # Generated PDF reports
├── config.py           # Portfolio config, allocations, thresholds
├── main.py             # CLI entry point
├── requirements.txt
└── .env.example
```

## Setup

```bash
# 1. Clone and create virtual environment
python -m venv .venv
source .venv/bin/activate       # Linux/Mac
.venv\Scripts\activate          # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
# Run one agent cycle (threshold strategy)
python main.py

# Use calendar strategy
python main.py --strategy calendar

# Simulate 30 days of rebalancing
python main.py --simulate-days 30

# Generate PDF report from current portfolio (no agent run)
python main.py --report

# Launch Streamlit dashboard
streamlit run dashboard/app.py

# Run tests
pytest tests/ -v
```

## Target Allocation

| Asset | Weight | Category |
|-------|--------|----------|
| AAPL | 12% | Equity |
| MSFT | 12% | Equity |
| GOOGL | 9% | Equity |
| AMZN | 9% | Equity |
| NVDA | 8% | Equity |
| TLT | 15% | Bonds |
| BND | 15% | Bonds |
| BTC-USD | 12% | Crypto |
| ETH-USD | 8% | Crypto |

## Agent Architecture

```
[observe] → fetch prices, compute metrics, evaluate strategy
[analyze] → Claude: summarize market state, identify anomalies
[decide]  → Claude: tool-calling loop (get_portfolio_state → get_market_data → execute_trade)
[execute] → post-trade validation, kill switch check
[audit]   → log cycle, generate PDF report
```

## Risk Controls

- **Kill Switch:** Activates if drawdown from peak exceeds 10% — all trading halts
- **Slippage:** 0.1% for equities/ETFs, 0.5% for crypto
- **Drift Threshold:** 5% deviation triggers rebalancing

## License

MIT
