"""Institutional News and Sentiment Ingestion Service."""

from __future__ import annotations

import yfinance as yf
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime

from ml.sentiment_service import SentimentAnalysisService
from services.data_lake_service import DataLakeService

class NewsSentimentService:
    """Fetches news and computes sentiment signals."""

    def __init__(self, sentiment_svc: Optional[SentimentAnalysisService] = None):
        self.sentiment_svc = sentiment_svc or SentimentAnalysisService(use_mock=True)
        self.lake = DataLakeService()

    def get_ticker_sentiment(self, ticker: str) -> Dict[str, Any]:
        """Fetch latest news for a ticker and compute aggregate sentiment."""
        try:
            t = yf.Ticker(ticker)
            news = t.news
            if not news:
                return {"ticker": ticker, "score": 0.0, "count": 0}
            
            # Extract headlines/summaries
            texts = [n.get("title", "") + ". " + n.get("summary", "") for n in news[:10]]
            results = self.sentiment_svc.batch_analyze(texts)
            avg_score = self.sentiment_svc.aggregate_sentiment(results)
            
            return {
                "ticker": ticker,
                "score": avg_score,
                "count": len(results),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            print(f"Error fetching news for {ticker}: {e}")
            return {"ticker": ticker, "score": 0.0, "count": 0, "error": str(e)}

    def sync_sentiment_to_lake(self, tickers: List[str]):
        """Compute sentiment for all tickers and save to Silver layer."""
        all_sentiments = []
        for ticker in tickers:
            res = self.get_ticker_sentiment(ticker)
            all_sentiments.append(res)
        
        # Save as a daily snapshot in Silver
        df = pd.DataFrame(all_sentiments)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        path = self.lake.silver_path / f"sentiment_{today}.parquet"
        df.to_parquet(path)
        return str(path)

    def get_mock_historical_sentiment(self, tickers: List[str], dates: pd.DatetimeIndex) -> pd.DataFrame:
        """Generate mock historical sentiment for backtesting purposes."""
        import numpy as np
        data = {}
        for t in tickers:
            # Random walk sentiment to simulate regimes
            scores = np.random.uniform(-0.5, 0.5, len(dates))
            data[t] = scores
        
        return pd.DataFrame(data, index=dates)
