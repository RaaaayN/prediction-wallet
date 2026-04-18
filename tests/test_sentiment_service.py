"""Tests for sentiment analysis service."""

import pytest
from ml.sentiment_service import SentimentAnalysisService

@pytest.fixture
def mock_sentiment_svc():
    return SentimentAnalysisService(use_mock=True)

def test_analyze_sentiment_bullish(mock_sentiment_svc):
    res = mock_sentiment_svc.analyze_sentiment("Markets are bullish today with high growth.")
    assert res["composite"] > 0.5
    assert res["positive"] > res["negative"]

def test_analyze_sentiment_bearish(mock_sentiment_svc):
    res = mock_sentiment_svc.analyze_sentiment("A massive crash is coming, bearish outlook.")
    assert res["composite"] < -0.5
    assert res["negative"] > res["positive"]

def test_analyze_sentiment_neutral(mock_sentiment_svc):
    res = mock_sentiment_svc.analyze_sentiment("The weather is nice today.")
    assert abs(res["composite"]) < 0.1
    assert res["neutral"] > res["positive"]

def test_aggregate_sentiment(mock_sentiment_svc):
    results = [
        {"composite": 0.8},
        {"composite": 0.2},
        {"composite": -0.4}
    ]
    avg = mock_sentiment_svc.aggregate_sentiment(results)
    assert avg == pytest.approx(0.2)
