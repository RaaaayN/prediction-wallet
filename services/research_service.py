"""Local research gateway used as fallback when MCP is unavailable."""

from __future__ import annotations


class LocalResearchGateway:
    """Generate a compact market commentary from local metrics."""

    def summarize(self, tickers: list[str], market_snapshot: dict) -> str:
        metrics = market_snapshot.get("metrics", {})
        if not tickers:
            return "No tickers requested."
        notes = []
        for ticker in tickers:
            metric = metrics.get(ticker, {})
            if not metric:
                notes.append(f"{ticker}: no recent data available")
                continue
            vol = metric.get("volatility_30d", 0)
            ytd = metric.get("ytd_return", 0)
            posture = "elevated volatility" if vol > 0.35 else "normal volatility"
            notes.append(f"{ticker}: {posture}, YTD {ytd:+.1%}")
        return "; ".join(notes)
