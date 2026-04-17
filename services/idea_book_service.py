"""Idea book persistence and profile-seeded research helpers."""

from __future__ import annotations

from agents.models import IdeaBookEntry, IdeaProposal
from config import HEDGE_FUND_PROFILE, MARKET_DB
from db.repository import get_idea_book, upsert_idea_book
from engine.hedge_fund import score_idea


class IdeaBookService:
    def __init__(self, db_path: str = MARKET_DB):
        self.db_path = db_path

    def seed_from_profile(self) -> list[IdeaBookEntry]:
        ideas = HEDGE_FUND_PROFILE.get("ideas") or []
        universe = HEDGE_FUND_PROFILE.get("universe") or {}
        entries: list[dict] = []
        for idea in ideas:
            meta = universe.get(idea.get("ticker"), {}) or {}
            entries.append({
                **idea,
                "source": "profile_seed",
                "crowded_score": float(meta.get("crowded_score", 0.0)),
                "short_squeeze_risk": bool(meta.get("short_squeeze_risk", False)),
            })
        if entries:
            upsert_idea_book(entries, db_path=self.db_path)
        return [IdeaBookEntry(**entry) for entry in get_idea_book(db_path=self.db_path)]

    def list_entries(self, status: str | None = None) -> list[IdeaBookEntry]:
        rows = get_idea_book(status=status, db_path=self.db_path)
        if not rows and (HEDGE_FUND_PROFILE.get("ideas") or []):
            return self.seed_from_profile()
        return [IdeaBookEntry(**row) for row in rows]

    def research(self, metrics: dict[str, dict]) -> list[IdeaProposal]:
        proposals: list[IdeaProposal] = []
        for entry in self.list_entries():
            scored = score_idea(
                entry.model_dump(),
                price_metrics=(metrics.get(entry.ticker) or {}),
                crowded_score=entry.crowded_score,
            )
            proposals.append(IdeaProposal(**scored))
        return proposals
