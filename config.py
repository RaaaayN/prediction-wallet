"""Central configuration for the autonomous portfolio rebalancing agent."""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# AI provider: "gemini" or "anthropic"
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")

# Portfolio target allocation (must sum to 1.0)
TARGET_ALLOCATION = {
    # Equities ~50%
    "AAPL": 0.12,
    "MSFT": 0.12,
    "GOOGL": 0.09,
    "AMZN": 0.09,
    "NVDA": 0.08,
    # Bonds ~30%
    "TLT": 0.15,
    "BND": 0.15,
    # Crypto ~20%
    "BTC-USD": 0.12,
    "ETH-USD": 0.08,
}

# Verify allocation sums to 1.0
assert abs(sum(TARGET_ALLOCATION.values()) - 1.0) < 1e-9, "TARGET_ALLOCATION must sum to 1.0"

# Capital
INITIAL_CAPITAL = 100_000.0

# Rebalancing thresholds
DRIFT_THRESHOLD = 0.05      # 5% drift triggers threshold rebalancing
CALENDAR_FREQUENCY = "weekly"  # "weekly" or "monthly" for calendar strategy

# Risk management
KILL_SWITCH_DRAWDOWN = 0.10  # 10% drawdown from peak → emergency stop

# Slippage model
SLIPPAGE_EQUITIES = 0.001   # 0.1% bid/ask spread for equities/ETFs
SLIPPAGE_CRYPTO = 0.005     # 0.5% for crypto

CRYPTO_TICKERS = {"BTC-USD", "ETH-USD"}

# Data paths
DATA_DIR = "data"
MARKET_DB = "data/market.db"
PORTFOLIO_FILE = "data/portfolio.json"
TRADES_LOG = "data/trades.log"
REPORTS_DIR = "data/reports"

# Market data
BENCHMARK_TICKER = "^GSPC"
DEFAULT_HISTORY_DAYS = 90
VOLATILITY_WINDOW = 30
RISK_FREE_RATE = 0.02  # 2% annual

# Claude model
CLAUDE_MODEL = "claude-sonnet-4-6"

# Gemini model
GEMINI_MODEL = "gemini-2.5-flash-lite"
