"""Market data service with structured cache metadata."""

from __future__ import annotations

import asyncio
import sqlite3
import time

import pandas as pd

from config import BENCHMARK_TICKER, MARKET_DB
from db.schema import init_db
from utils.time import utc_now_iso


def _coerce_single_series(data: pd.DataFrame, column_name: str) -> pd.Series:
    """Return a single price series even if duplicate column labels are present."""
    selected = data[column_name]
    if isinstance(selected, pd.DataFrame):
        # yfinance can occasionally return duplicated labels after flattening a
        # MultiIndex result; keep the first non-empty column deterministically.
        selected = selected.iloc[:, 0]
    return pd.to_numeric(selected, errors="coerce")


def _normalize_ohlcv_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance outputs to a stable single-ticker OHLCV schema."""
    normalized = data.copy()
    if isinstance(normalized.columns, pd.MultiIndex):
        columns = list(normalized.columns)
        preferred_level = None
        for level in range(normalized.columns.nlevels):
            values = normalized.columns.get_level_values(level)
            if {"Open", "High", "Low", "Close"}.issubset(set(values)):
                preferred_level = level
                break
        if preferred_level is None:
            preferred_level = 0
        normalized.columns = normalized.columns.get_level_values(preferred_level)

    normalized = normalized.loc[:, ~normalized.columns.duplicated()].copy()
    if "Close" not in normalized.columns and "Adj Close" in normalized.columns:
        normalized["Close"] = pd.to_numeric(normalized["Adj Close"], errors="coerce")
    return normalized


def add_technical_indicators(data: pd.DataFrame) -> pd.DataFrame:
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


def _require_yfinance():
    import yfinance as yf

    return yf


class MarketService:
    """Wrap yfinance access and record refresh metadata in SQLite."""

    def __init__(self, db_path: str = MARKET_DB, min_refresh_interval_seconds: int = 900):
        self.db_path = db_path
        self.min_refresh_interval_seconds = min_refresh_interval_seconds
        init_db(self.db_path)

    def fetch_and_store(self, tickers: list[str], period: str = "1y", force: bool = False) -> dict[str, pd.DataFrame]:
        results = {}
        for ticker in tickers:
            if not force and not self._needs_refresh(ticker):
                cached = self._load_from_db(ticker)
                if cached is not None and not cached.empty:
                    results[ticker] = cached
                    continue
            try:
                df = self._download(ticker, period)
                if df.empty:
                    self._record_refresh(ticker, False, "No data returned")
                    continue
                df = add_technical_indicators(df)
                self._save_to_db(df, ticker)
                self._record_refresh(ticker, True, "")
                results[ticker] = df
                time.sleep(0.3)
            except Exception as exc:
                self._record_refresh(ticker, False, str(exc))
        return results

    async def fetch_and_store_async(
        self,
        tickers: list[str],
        period: str = "1y",
        force: bool = False,
    ) -> tuple[dict[str, pd.DataFrame], dict[str, float]]:
        async def _fetch_one(ticker: str) -> tuple[str, pd.DataFrame | None, float]:
            started = time.perf_counter()
            if not force and not self._needs_refresh(ticker):
                cached = self._load_from_db(ticker)
                if cached is not None and not cached.empty:
                    return ticker, cached, round((time.perf_counter() - started) * 1000, 2)
            try:
                df = await asyncio.to_thread(self._download, ticker, period)
                if df.empty:
                    self._record_refresh(ticker, False, "No data returned")
                    return ticker, None, round((time.perf_counter() - started) * 1000, 2)
                df = add_technical_indicators(df)
                self._save_to_db(df, ticker)
                self._record_refresh(ticker, True, "")
                return ticker, df, round((time.perf_counter() - started) * 1000, 2)
            except Exception as exc:
                self._record_refresh(ticker, False, str(exc))
                return ticker, None, round((time.perf_counter() - started) * 1000, 2)

        results: dict[str, pd.DataFrame] = {}
        latencies: dict[str, float] = {}
        for ticker, df, latency_ms in await asyncio.gather(*[_fetch_one(ticker) for ticker in tickers]):
            latencies[ticker] = latency_ms
            if df is not None and not df.empty:
                results[ticker] = df
        return results, latencies

    def get_latest_prices(self, tickers: list[str]) -> dict[str, float]:
        prices = {}
        yf = _require_yfinance()
        for ticker in tickers:
            try:
                df = self._load_from_db(ticker)
                if df is not None and not df.empty:
                    prices[ticker] = float(df["Close"].iloc[-1])
                else:
                    live = yf.Ticker(ticker).fast_info
                    prices[ticker] = float(live.get("lastPrice", live.get("regularMarketPrice", 0)))
            except Exception:
                prices[ticker] = 0.0
        return prices

    def get_historical(self, ticker: str, days: int = 90) -> pd.DataFrame:
        df = self._load_from_db(ticker)
        if df is None or df.empty:
            return pd.DataFrame()
        return df.tail(days)

    def get_benchmark(self, period: str = "1y") -> pd.DataFrame:
        df = self._download(BENCHMARK_TICKER, period)
        if not df.empty and isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df

    def refresh_prices(self, tickers: list[str]) -> dict[str, float]:
        prices = {}
        yf = _require_yfinance()
        for ticker in tickers:
            try:
                info = yf.Ticker(ticker).fast_info
                price = info.get("lastPrice") or info.get("regularMarketPrice")
                if price:
                    prices[ticker] = float(price)
            except Exception:
                pass
        return prices

    def get_refresh_status(self) -> list[dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT ticker, refreshed_at, success, error FROM market_data_status ORDER BY ticker"
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _download(self, ticker: str, period: str) -> pd.DataFrame:
        yf = _require_yfinance()
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        return _normalize_ohlcv_columns(df)

    def _save_to_db(self, df: pd.DataFrame, ticker: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            df.to_sql(f"prices__{ticker}", conn, if_exists="replace", index=True)

    def _load_from_db(self, ticker: str) -> pd.DataFrame | None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                return pd.read_sql(
                    f'SELECT * FROM "prices__{ticker}"',
                    conn,
                    index_col="Date",
                    parse_dates=["Date"],
                )
        except Exception:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    return pd.read_sql(
                        f'SELECT * FROM "{ticker}"',
                        conn,
                        index_col="Date",
                        parse_dates=["Date"],
                    )
            except Exception:
                return None

    def _needs_refresh(self, ticker: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT refreshed_at FROM market_data_status WHERE ticker = ?", (ticker,)).fetchone()
            if row is None or not row[0]:
                return True
            refreshed_at = pd.to_datetime(row[0], utc=True)
            age = (pd.Timestamp.utcnow() - refreshed_at).total_seconds()
            return age >= self.min_refresh_interval_seconds
        except Exception:
            return True

    def _record_refresh(self, ticker: str, success: bool, error: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO market_data_status (ticker, refreshed_at, success, error)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    refreshed_at = excluded.refreshed_at,
                    success = excluded.success,
                    error = excluded.error
                """,
                (ticker, utc_now_iso(), int(success), error),
            )
            conn.commit()
