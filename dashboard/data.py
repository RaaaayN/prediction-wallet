"""Dashboard data loading helpers."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from config import REPORTS_DIR, TARGET_ALLOCATION
from db import get_agent_runs, get_decision_traces, get_executions, get_history, get_market_data_status
from execution.simulator import TradeSimulator
from market.fetcher import MarketDataService


@st.cache_data(ttl=30)
def load_portfolio() -> dict:
    return TradeSimulator().load_portfolio()


@st.cache_data(ttl=30)
def load_prices() -> dict[str, float]:
    return MarketDataService().get_latest_prices(list(TARGET_ALLOCATION.keys()))


@st.cache_data(ttl=60)
def load_trades() -> list[dict]:
    df = get_executions(limit=500)
    if not df.empty:
        return df.to_dict("records")
    return TradeSimulator().get_trade_history()


@st.cache_data(ttl=60)
def load_history_df() -> pd.DataFrame:
    return get_history(days=365)


@st.cache_data(ttl=60)
def load_agent_runs() -> list[dict]:
    return get_agent_runs(limit=20)


@st.cache_data(ttl=60)
def load_market_status() -> list[dict]:
    return get_market_data_status()


@st.cache_data(ttl=60)
def load_decision_traces() -> list[dict]:
    return get_decision_traces(limit=100)


def compute_summary(portfolio: dict, prices: dict) -> dict:
    positions = portfolio.get("positions", {})
    cash = portfolio.get("cash", 0.0)
    peak = portfolio.get("peak_value", cash)
    market_value = sum(qty * prices.get(t, 0) for t, qty in positions.items())
    total = market_value + cash
    drawdown = (total - peak) / peak if peak > 0 else 0
    return {"total": total, "cash": cash, "market_value": market_value, "peak": peak, "drawdown": drawdown}


def list_reports() -> list[str]:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return sorted([f for f in os.listdir(REPORTS_DIR) if f.endswith(".pdf")], reverse=True)
