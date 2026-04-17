"""Central configuration — compatibility shim that reads from settings.py + active profile YAML.

All existing imports (from config import TARGET_ALLOCATION, ...) continue to work unchanged.
Switch profiles at runtime via the PORTFOLIO_PROFILE env var or --profile CLI flag.
"""

from settings import settings
from portfolio_loader import get_active_profile

# ---------------------------------------------------------------------------
# Scalar settings from pydantic-settings (.env / env vars)
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY: str = settings.anthropic_api_key
GEMINI_API_KEY: str = settings.gemini_api_key
AI_PROVIDER: str = settings.ai_provider
CLAUDE_MODEL: str = settings.claude_model
GEMINI_MODEL: str = settings.gemini_model

DATA_DIR: str = settings.data_dir
DATABASE_URL: str | None = settings.database_url
USE_POSTGRES: bool = bool(DATABASE_URL)
MARKET_DB: str = settings.market_db
PORTFOLIO_FILE: str = settings.portfolio_file
TRADES_LOG: str = settings.trades_log
REPORTS_DIR: str = settings.reports_dir
MAX_TRADES_PER_CYCLE: int = settings.max_trades_per_cycle
MAX_ORDER_FRACTION_OF_PORTFOLIO: float = settings.max_order_fraction_of_portfolio
MARKET_DATA_TTL_SECONDS: int = settings.market_data_ttl_seconds
AGENT_BACKEND: str = settings.agent_backend
EXECUTION_MODE: str = settings.execution_mode
MCP_PROFILE: str = settings.mcp_profile
MCP_TIMEOUT_SECONDS: int = settings.mcp_timeout_seconds

BENCHMARK_TICKER: str = settings.benchmark_ticker
DEFAULT_HISTORY_DAYS: int = 90
VOLATILITY_WINDOW: int = settings.volatility_window
RISK_FREE_RATE: float = settings.risk_free_rate

# ---------------------------------------------------------------------------
# Profile-based settings (target allocation, thresholds, slippage)
# ---------------------------------------------------------------------------

_profile = get_active_profile()

TARGET_ALLOCATION: dict[str, float] = _profile["target_allocation"]
INITIAL_CAPITAL: float = _profile["initial_capital"]
DRIFT_THRESHOLD: float = _profile["drift_threshold"]
KILL_SWITCH_DRAWDOWN: float = _profile["kill_switch_drawdown"]
SLIPPAGE_EQUITIES: float = _profile["slippage_equities"]
SLIPPAGE_CRYPTO: float = _profile["slippage_crypto"]
HEDGE_FUND_PROFILE: dict = _profile.get("hedge_fund") or {}

# ---------------------------------------------------------------------------
# Derived constants
# ---------------------------------------------------------------------------

CRYPTO_TICKERS: set[str] = {t for t in TARGET_ALLOCATION if "USD" in t and "-" in t}

SECTOR_MAP: dict[str, str] = {
    "AAPL": "tech", "MSFT": "tech", "GOOGL": "tech", "AMZN": "tech", "NVDA": "tech",
    "TLT": "bonds", "BND": "bonds",
    "BTC-USD": "crypto", "ETH-USD": "crypto",
}

MAX_SECTOR_CONCENTRATION: float = 0.55  # soft block: 5pp above the 50% tech target

CALENDAR_FREQUENCY: str = "weekly"  # "weekly" or "monthly" for CalendarStrategy

_target_sum = sum(TARGET_ALLOCATION.values())
assert _target_sum == 0.0 or abs(_target_sum - 1.0) < 1e-6, (
    f"Profile '{_profile['name']}' TARGET_ALLOCATION must sum to 1.0 or be a zeroed hedge-fund seed book"
)
