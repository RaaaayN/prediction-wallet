"""Persistence adapters for portfolio and trade logs."""

from __future__ import annotations

import json
import os
from dataclasses import asdict

from config import INITIAL_CAPITAL, PORTFOLIO_FILE, TRADES_LOG
from utils.time import utc_now_iso


class PortfolioStore:
    """File-backed portfolio state store."""

    def __init__(self, portfolio_file: str = PORTFOLIO_FILE):
        self.portfolio_file = portfolio_file

    def load(self) -> dict:
        try:
            with open(self.portfolio_file, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return self.default_portfolio()

    def save(self, portfolio: dict) -> None:
        os.makedirs(os.path.dirname(self.portfolio_file), exist_ok=True)
        with open(self.portfolio_file, "w", encoding="utf-8") as f:
            json.dump(portfolio, f, indent=2, default=str)

    @staticmethod
    def default_portfolio() -> dict:
        return {
            "positions": {},
            "cash": INITIAL_CAPITAL,
            "peak_value": INITIAL_CAPITAL,
            "last_rebalanced": None,
            "history": [],
            "created_at": utc_now_iso(),
        }


class TradeLogStore:
    """Append-only JSONL trade log."""

    def __init__(self, trades_log: str = TRADES_LOG):
        self.trades_log = trades_log

    def append(self, payload: dict | object) -> None:
        os.makedirs(os.path.dirname(self.trades_log), exist_ok=True)
        data = asdict(payload) if hasattr(payload, "__dataclass_fields__") else payload
        with open(self.trades_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, default=str) + "\n")

    def read_all(self) -> list[dict]:
        try:
            with open(self.trades_log, encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            return []
