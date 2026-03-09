"""Portfolio and market metrics calculations."""

import numpy as np
import pandas as pd

from config import VOLATILITY_WINDOW, RISK_FREE_RATE


class PortfolioMetrics:
    """Compute key risk/return metrics from price or return series."""

    @staticmethod
    def calculate_returns(prices_df: pd.DataFrame) -> pd.DataFrame:
        """Compute daily log returns from a prices DataFrame."""
        return prices_df.pct_change().dropna()

    @staticmethod
    def calculate_volatility(returns: pd.Series | pd.DataFrame, window: int = VOLATILITY_WINDOW) -> pd.Series | pd.DataFrame:
        """Rolling annualized volatility (std * sqrt(252))."""
        return returns.rolling(window=window).std() * np.sqrt(252)

    @staticmethod
    def calculate_sharpe(returns: pd.Series, rf: float = RISK_FREE_RATE) -> float:
        """Annualized Sharpe ratio for a return series."""
        if returns.std() == 0:
            return 0.0
        excess = returns.mean() * 252 - rf
        vol = returns.std() * np.sqrt(252)
        return float(excess / vol)

    @staticmethod
    def calculate_correlations(returns: pd.DataFrame) -> pd.DataFrame:
        """Pearson correlation matrix of returns."""
        return returns.corr()

    @staticmethod
    def calculate_drawdown(values: pd.Series) -> dict:
        """Compute drawdown series and maximum drawdown from a value series."""
        peak = values.cummax()
        drawdown = (values - peak) / peak
        max_drawdown = float(drawdown.min())
        return {"drawdown_series": drawdown, "max_drawdown": max_drawdown}

    @staticmethod
    def current_drawdown(current_value: float, peak_value: float) -> float:
        """Drawdown of current value from historical peak."""
        if peak_value <= 0:
            return 0.0
        return (current_value - peak_value) / peak_value

    @staticmethod
    def ticker_metrics(df: pd.DataFrame, rf: float = RISK_FREE_RATE) -> dict:
        """
        Compute a summary dict for a single ticker's historical DataFrame.
        Returns: last_price, volatility_30d, ytd_return, sharpe
        """
        if df.empty or "Close" not in df.columns:
            return {}

        close = df["Close"].dropna()
        returns = close.pct_change().dropna()

        last_price = float(close.iloc[-1])

        # 30-day volatility (annualized)
        vol_30 = float(returns.tail(30).std() * np.sqrt(252)) if len(returns) >= 30 else float(returns.std() * np.sqrt(252))

        # YTD return
        start_of_year = close[close.index.year == close.index[-1].year].iloc[0] if not close.empty else close.iloc[0]
        ytd_return = float((close.iloc[-1] / start_of_year) - 1)

        # Sharpe
        sharpe = PortfolioMetrics.calculate_sharpe(returns, rf)

        return {
            "last_price": last_price,
            "volatility_30d": vol_30,
            "ytd_return": ytd_return,
            "sharpe": sharpe,
        }
