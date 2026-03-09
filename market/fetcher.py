"""Market data fetching and storage — adapted from src/data_collection.py."""

import sqlite3
import time
import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from config import MARKET_DB, DATA_DIR, BENCHMARK_TICKER


def add_technical_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """Add SMA20, EMA20, RSI14, Bollinger Bands, MACD to a price DataFrame."""
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    close = data["Close"]

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


class MarketDataService:
    """Fetches market data via yfinance and stores it in SQLite."""

    def __init__(self, db_path: str = MARKET_DB):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_and_store(self, tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
        """Download price data for all tickers and persist to SQLite."""
        results = {}
        for ticker in tickers:
            try:
                df = self._download(ticker, period)
                if df.empty:
                    print(f"[fetcher] No data for {ticker}, skipping.")
                    continue
                df = add_technical_indicators(df)
                self._save_to_db(df, ticker)
                results[ticker] = df
                time.sleep(0.3)
            except Exception as exc:
                print(f"[fetcher] Error fetching {ticker}: {exc}")
        return results

    def get_latest_prices(self, tickers: list[str]) -> dict[str, float]:
        """Return the most recent closing price for each ticker."""
        prices = {}
        for ticker in tickers:
            try:
                df = self._load_from_db(ticker)
                if df is not None and not df.empty:
                    prices[ticker] = float(df["Close"].iloc[-1])
                else:
                    # Fallback: live fetch
                    live = yf.Ticker(ticker).fast_info
                    prices[ticker] = float(live.get("lastPrice", live.get("regularMarketPrice", 0)))
            except Exception as exc:
                print(f"[fetcher] Could not get price for {ticker}: {exc}")
                prices[ticker] = 0.0
        return prices

    def get_historical(self, ticker: str, days: int = 90) -> pd.DataFrame:
        """Return a DataFrame with OHLCV + indicators for the last `days` rows."""
        df = self._load_from_db(ticker)
        if df is None or df.empty:
            return pd.DataFrame()
        return df.tail(days)

    def get_benchmark(self, period: str = "1y") -> pd.DataFrame:
        """Fetch S&P500 benchmark data."""
        df = self._download(BENCHMARK_TICKER, period)
        if not df.empty and isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df

    def refresh_prices(self, tickers: list[str]) -> dict[str, float]:
        """Live-fetch latest prices without storing (for real-time use)."""
        prices = {}
        for ticker in tickers:
            try:
                info = yf.Ticker(ticker).fast_info
                price = info.get("lastPrice") or info.get("regularMarketPrice")
                if price:
                    prices[ticker] = float(price)
            except Exception:
                pass
        return prices

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _download(self, ticker: str, period: str) -> pd.DataFrame:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df

    def _save_to_db(self, df: pd.DataFrame, ticker: str) -> None:
        conn = sqlite3.connect(self.db_path)
        df.to_sql(ticker, conn, if_exists="replace", index=True)
        conn.close()

    def _load_from_db(self, ticker: str) -> pd.DataFrame | None:
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql(f'SELECT * FROM "{ticker}"', conn, index_col="Date", parse_dates=["Date"])
            conn.close()
            return df
        except Exception:
            return None
