"""Shared execution types."""

import uuid
from dataclasses import dataclass


@dataclass
class TradeResult:
    trade_id: str
    action: str
    ticker: str
    quantity: float
    market_price: float
    fill_price: float
    cost: float
    timestamp: str
    reason: str
    success: bool
    error: str = ""

    @classmethod
    def build(cls, **kwargs) -> "TradeResult":
        trade_id = kwargs.pop("trade_id", "") or str(uuid.uuid4())[:8]
        return cls(trade_id=trade_id, **kwargs)
