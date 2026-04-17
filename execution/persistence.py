"""Persistence adapters for portfolio and trade logs."""

from __future__ import annotations

import json
import os
from dataclasses import asdict

from runtime_context import build_default_portfolio, build_runtime_context
from utils.time import utc_now_iso


class PortfolioStore:
    """File-backed portfolio state store."""

    def __init__(self, portfolio_file: str | None = None, *, profile_name: str | None = None, runtime_context=None):
        self.runtime_context = runtime_context or build_runtime_context(profile_name)
        self.portfolio_file = portfolio_file or self.runtime_context.portfolio_file

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
    def default_portfolio(initial_capital: float = 100_000.0) -> dict:
        portfolio = build_default_portfolio(initial_capital)
        portfolio.setdefault("created_at", utc_now_iso())
        return portfolio


class TradeLogStore:
    """Append-only JSONL trade log."""

    def __init__(self, trades_log: str | None = None, *, profile_name: str | None = None, runtime_context=None):
        self.runtime_context = runtime_context or build_runtime_context(profile_name)
        self.trades_log = trades_log or self.runtime_context.trades_log

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
