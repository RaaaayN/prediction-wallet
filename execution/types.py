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
    side: str = "long"
    idea_id: str | None = None
    sleeve: str = "core_longs"
    exposure_before: float = 0.0
    exposure_after: float = 0.0
    gross_impact: float = 0.0
    net_impact: float = 0.0

    @classmethod
    def build(cls, **kwargs) -> "TradeResult":
        trade_id = kwargs.pop("trade_id", "") or str(uuid.uuid4())[:8]
        return cls(trade_id=trade_id, **kwargs)
