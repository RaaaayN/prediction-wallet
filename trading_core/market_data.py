"""Market data handler adapting MarketService to canonical MarketPrice objects."""

from __future__ import annotations
from typing import Dict, List, Optional
from trading_core.models import MarketPrice, MarketDataSource, MarketDataFreshness
from trading_core.security_master import SecurityMaster
from services.market_service import MarketService
from utils.time import utc_now_iso
from datetime import datetime, timezone, timedelta

class MarketDataHandler:
    """Provides canonical market prices using the underlying MarketService."""

    def __init__(self, market_service: MarketService, security_master: SecurityMaster):
        self.market_service = market_service
        self.security_master = security_master

    def get_market_price(self, symbol: str) -> MarketPrice:
        """Fetch canonical MarketPrice for a symbol."""
        instrument = self.security_master.get_or_create_by_symbol(symbol)
        prices = self.market_service.get_latest_prices([symbol])
        price = prices.get(symbol, 0.0)
        
        # Determine freshness
        refresh_status = self.market_service.get_refresh_status()
        ticker_status = next((s for s in refresh_status if s["ticker"] == symbol), None)
        
        freshness = MarketDataFreshness.UNKNOWN
        as_of = utc_now_iso()
        is_stale = False
        
        if ticker_status and ticker_status.get("refreshed_at"):
            as_of = ticker_status["refreshed_at"]
            threshold = datetime.now(timezone.utc) - timedelta(hours=24)
            try:
                ts = datetime.fromisoformat(as_of)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts > threshold:
                    freshness = MarketDataFreshness.FRESH
                else:
                    freshness = MarketDataFreshness.STALE
                    is_stale = True
            except (ValueError, AttributeError):
                freshness = MarketDataFreshness.UNKNOWN
        
        return MarketPrice(
            instrument_id=instrument.instrument_id,
            symbol=symbol,
            as_of=as_of,
            price=price,
            source=MarketDataSource.YFINANCE,
            freshness=freshness,
            is_stale=is_stale,
            status="ok" if price > 0 else "error"
        )

    def get_prices(self, symbols: List[str]) -> Dict[str, MarketPrice]:
        """Fetch multiple canonical MarketPrice objects."""
        return {symbol: self.get_market_price(symbol) for symbol in symbols}
