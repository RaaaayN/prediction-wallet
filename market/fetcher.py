"""Backward-compatible wrapper around the market service."""

from __future__ import annotations

import pandas as pd

from config import MARKET_DB, MARKET_DATA_TTL_SECONDS
from services.market_service import MarketService, _coerce_single_series, _normalize_ohlcv_columns


def add_technical_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """Add SMA20, EMA20, RSI14, Bollinger Bands, MACD to a price DataFrame."""
    data = _normalize_ohlcv_columns(data)
    close = _coerce_single_series(data, "Close")
    data["SMA20"] = close.rolling(window=20).mean()
    data["EMA20"] = close.ewm(span=20, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    data["RSI14"] = 100 - (100 / (1 + rs))

    rolling_std = close.rolling(window=20).std()
    data["Bollinger_Upper"] = data["SMA20"] + 2 * rolling_std
    data["Bollinger_Lower"] = data["SMA20"] - 2 * rolling_std

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    data["MACD"] = ema12 - ema26
    data["MACD_Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()
    return data


class MarketDataService(MarketService):
    """Compatibility alias for the new market service."""

    def __init__(self, db_path: str = MARKET_DB):
        super().__init__(db_path=db_path, min_refresh_interval_seconds=MARKET_DATA_TTL_SECONDS)
