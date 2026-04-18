"""Central configuration — compatibility shim that reads from settings.py + active profile YAML.

All existing imports (from config import TARGET_ALLOCATION, ...) continue to work unchanged.
Switch profiles at runtime via the PORTFOLIO_PROFILE env var or --profile CLI flag.
"""

import sys
from settings import settings
from portfolio_loader import get_active_profile

# ---------------------------------------------------------------------------
# Dynamic properties handler
# ---------------------------------------------------------------------------

class ConfigModule(sys.modules[__name__].__class__):
    def __getattr__(self, name):
        # 1. Check settings (env vars / defaults)
        if hasattr(settings, name.lower()):
            return getattr(settings, name.lower())
        
        # 2. Check active profile
        profile = get_active_profile()
        if name == "TARGET_ALLOCATION": return profile["target_allocation"]
        if name == "INITIAL_CAPITAL": return profile["initial_capital"]
        if name == "DRIFT_THRESHOLD": return profile["drift_threshold"]
        if name == "KILL_SWITCH_DRAWDOWN": return profile["kill_switch_drawdown"]
        if name == "SLIPPAGE_EQUITIES": return profile["slippage_equities"]
        if name == "SLIPPAGE_CRYPTO": return profile["slippage_crypto"]
        if name == "HEDGE_FUND_PROFILE": return profile.get("hedge_fund") or {}

        # 3. Special derived / hardcoded
        if name == "USE_POSTGRES": return bool(self.DATABASE_URL)
        if name == "DATABASE_URL": return settings.database_url
        if name == "ALLOWED_ORIGINS": return [o.strip() for o in settings.allowed_origins.split(",")]
        if name == "CRYPTO_TICKERS": 
            ta = profile["target_allocation"]
            return {t for t in ta if "USD" in t and "-" in t}
        if name == "SECTOR_MAP":
            return {
                "AAPL": "tech", "MSFT": "tech", "GOOGL": "tech", "AMZN": "tech", "NVDA": "tech",
                "TLT": "bonds", "BND": "bonds",
                "BTC-USD": "crypto", "ETH-USD": "crypto",
            }
        if name == "MAX_SECTOR_CONCENTRATION": return 0.55
        if name == "CALENDAR_FREQUENCY": return "weekly"
        if name == "DEFAULT_HISTORY_DAYS": return 90
        
        # Fallback to module globals (like this class itself)
        if name in globals():
            return globals()[name]
            
        raise AttributeError(f"module {__name__} has no attribute {name}")

# This trick replaces the module with a class instance so __getattr__ works globally
sys.modules[__name__].__class__ = ConfigModule

# ---------------------------------------------------------------------------
# Type hints for IDEs
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str
GEMINI_API_KEY: str
AI_PROVIDER: str
CLAUDE_MODEL: str
GEMINI_MODEL: str
DATA_DIR: str
DATABASE_URL: str | None
USE_POSTGRES: bool
MARKET_DB: str
PORTFOLIO_FILE: str
TRADES_LOG: str
REPORTS_DIR: str
MAX_TRADES_PER_CYCLE: int
MAX_ORDER_FRACTION_OF_PORTFOLIO: float
MARKET_DATA_TTL_SECONDS: int
API_KEY_ADMIN: str
API_KEY_TRADER: str
API_KEY_VIEWER: str
ALLOWED_ORIGINS: list[str]
TRADING_CORE_ENABLED: bool
AGENT_BACKEND: str
EXECUTION_MODE: str
MCP_PROFILE: str
MCP_TIMEOUT_SECONDS: int
BENCHMARK_TICKER: str
DEFAULT_HISTORY_DAYS: int
VOLATILITY_WINDOW: int
RISK_FREE_RATE: float
TARGET_ALLOCATION: dict[str, float]
INITIAL_CAPITAL: float
DRIFT_THRESHOLD: float
KILL_SWITCH_DRAWDOWN: float
SLIPPAGE_EQUITIES: float
SLIPPAGE_CRYPTO: float
HEDGE_FUND_PROFILE: dict
CRYPTO_TICKERS: set[str]
SECTOR_MAP: dict[str, str]
MAX_SECTOR_CONCENTRATION: float
CALENDAR_FREQUENCY: str
