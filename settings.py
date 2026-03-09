"""Central settings via pydantic-settings — reads from .env and environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API keys
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # AI provider: "gemini" or "anthropic"
    ai_provider: str = "gemini"

    # Model names
    gemini_model: str = "gemini-2.5-flash-lite"
    claude_model: str = "claude-sonnet-4-6"

    # Active portfolio profile (matches a file in profiles/)
    portfolio_profile: str = "balanced"

    # Data paths
    data_dir: str = "data"
    market_db: str = "data/market.db"
    portfolio_file: str = "data/portfolio.json"
    trades_log: str = "data/trades.log"
    reports_dir: str = "data/reports"

    # Market / metrics
    benchmark_ticker: str = "^GSPC"
    risk_free_rate: float = 0.02
    volatility_window: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
