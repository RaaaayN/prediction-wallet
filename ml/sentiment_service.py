"""Institutional Sentiment Analysis Service using FinBERT."""

from __future__ import annotations

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import List, Dict, Optional
import numpy as np

class SentimentAnalysisService:
    """Wraps FinBERT for financial sentiment inference."""

    def __init__(self, model_name: str = "ProsusAI/finbert", use_mock: bool = False):
        self.model_name = model_name
        self.use_mock = use_mock
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = None
        self.model = None
        
        if not use_mock:
            self._load_model()

    def _load_model(self):
        """Lazy load the model and tokenizer."""
        print(f"Loading {self.model_name} on {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name).to(self.device)
        self.model.eval()

    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of a single text snippet.
        
        Returns:
            Dict with 'positive', 'negative', 'neutral' scores and 'composite' (-1 to 1).
        """
        if self.use_mock:
            # Deterministic mock based on text content
            low_text = text.lower()
            if any(w in low_text for w in ["bullish", "growth", "profit", "up"]):
                return {"positive": 0.8, "negative": 0.1, "neutral": 0.1, "composite": 0.7}
            if any(w in low_text for w in ["bearish", "loss", "crash", "down"]):
                return {"positive": 0.1, "negative": 0.8, "neutral": 0.1, "composite": -0.7}
            return {"positive": 0.2, "negative": 0.2, "neutral": 0.6, "composite": 0.0}

        if not self.model:
            self._load_model()

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True).to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
            scores = torch.nn.functional.softmax(outputs.logits, dim=-1)
            scores = scores.detach().cpu().numpy()[0]

        # FinBERT labels: 0: positive, 1: negative, 2: neutral
        result = {
            "positive": float(scores[0]),
            "negative": float(scores[1]),
            "neutral": float(scores[2])
        }
        # Composite score: positive - negative
        result["composite"] = result["positive"] - result["negative"]
        return result

    def batch_analyze(self, texts: List[str]) -> List[Dict[str, float]]:
        """Analyze a batch of texts."""
        if not texts:
            return []
        return [self.analyze_sentiment(t) for t in texts]

    def aggregate_sentiment(self, results: List[Dict[str, float]]) -> float:
        """Compute an aggregated composite score from multiple results."""
        if not results:
            return 0.0
        return float(np.mean([r["composite"] for r in results]))
