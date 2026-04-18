"""Central settings via pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    ai_provider: str = "gemini"

    gemini_model: str = "gemini-2.5-flash-lite"
    claude_model: str = "claude-sonnet-4-6"

    portfolio_profile: str = "balanced"

    data_dir: str = "data"
    database_url: str | None = Field(
        default=None,
        description="PostgreSQL URL; unset keeps SQLite at market_db.",
    )
    market_db: str = "data/market.db"
    portfolio_file: str = "data/portfolio.json"
    trades_log: str = "data/trades.log"
    reports_dir: str = "data/reports"

    benchmark_ticker: str = "^GSPC"
    risk_free_rate: float = 0.045
    volatility_window: int = 30
    max_trades_per_cycle: int = Field(default=8)
    max_order_fraction_of_portfolio: float = Field(default=0.35)
    market_data_ttl_seconds: int = Field(default=900)

    # Security & API Auth (Fondation phase)
    # If no keys are set, the system defaults to "Super Admin" mode (Opt-in)
    api_key_admin: str = Field(default="", env="API_KEY_ADMIN")
    api_key_trader: str = Field(default="", env="API_KEY_TRADER")
    api_key_viewer: str = Field(default="", env="API_KEY_VIEWER")
    allowed_origins: str = Field(default="*", description="Comma-separated list of allowed CORS origins")

    agent_backend: str = Field(default="pydantic-ai")
    execution_mode: str = Field(default="simulate")
    mcp_profile: str = Field(default="none")
    mcp_timeout_seconds: int = Field(default=5)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
