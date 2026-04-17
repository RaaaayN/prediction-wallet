"""Idea book persistence and profile-seeded research helpers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import uuid

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from agents.models import IdeaBookEntry, IdeaProposal
from db.repository import get_idea_book, update_idea_book_entry, upsert_idea_book
from engine.hedge_fund import score_idea
from runtime_context import build_runtime_context


class IdeaGenerationCandidate(BaseModel):
    ticker: str
    side: str
    thesis: str
    catalyst: str
    time_horizon: str
    conviction: float = Field(ge=0.0, le=1.0)
    upside_case: str = ""
    downside_case: str = ""
    invalidation_rule: str
    sleeve: str = "core_longs"
    edge_source: str
    why_now: str
    key_risk: str
    supporting_signals: list[str] = Field(default_factory=list)
    evidence_quality: str = "medium"


class IdeaGenerationResponse(BaseModel):
    ideas: list[IdeaGenerationCandidate] = Field(default_factory=list)


class IdeaBookService:
    def __init__(self, db_path: str | None = None, *, profile_name: str | None = None, runtime_context=None):
        self.runtime_context = runtime_context or build_runtime_context(profile_name)
        self.db_path = db_path or self.runtime_context.market_db

    def seed_from_profile(self) -> list[IdeaBookEntry]:
        ideas = self.runtime_context.hedge_fund_profile.get("ideas") or []
        universe = self.runtime_context.hedge_fund_profile.get("universe") or {}
        entries: list[dict] = []
        for idea in ideas:
            meta = universe.get(idea.get("ticker"), {}) or {}
            entries.append({
                **idea,
                "source": "profile_seed",
                "crowded_score": float(meta.get("crowded_score", 0.0)),
                "short_squeeze_risk": bool(meta.get("short_squeeze_risk", False)),
                "edge_source": idea.get("edge_source", "fundamental"),
                "why_now": idea.get("why_now", idea.get("catalyst", "")),
                "key_risk": idea.get("key_risk", idea.get("downside_case", "")),
                "supporting_signals": idea.get("supporting_signals", []),
                "evidence_quality": idea.get("evidence_quality", "medium"),
                "review_status": idea.get("review_status", "approved"),
                "origin_cycle_id": idea.get("origin_cycle_id"),
                "llm_generated": bool(idea.get("llm_generated", False)),
            })
        if entries:
            upsert_idea_book(entries, db_path=self.db_path)
        return [IdeaBookEntry(**entry) for entry in get_idea_book(db_path=self.db_path)]

    def list_entries(
        self,
        status: str | None = None,
        review_status: str | None = None,
        llm_generated: bool | None = None,
    ) -> list[IdeaBookEntry]:
        rows = get_idea_book(status=status, review_status=review_status, llm_generated=llm_generated, db_path=self.db_path)
        if not rows and (self.runtime_context.hedge_fund_profile.get("ideas") or []):
            return self.seed_from_profile()
        return [IdeaBookEntry(**row) for row in rows]

    def research(self, metrics: dict[str, dict]) -> list[IdeaProposal]:
        proposals: list[IdeaProposal] = []
        approved_entries = [
            entry for entry in self.list_entries()
            if entry.review_status == "approved" and entry.status in {"watchlist", "investable", "portfolio"}
        ]
        for entry in approved_entries:
            scored = score_idea(
                entry.model_dump(),
                price_metrics=(metrics.get(entry.ticker) or {}),
                crowded_score=entry.crowded_score,
            )
            proposals.append(IdeaProposal(**scored))
        return proposals

    def generate_candidates(self, metrics: dict[str, dict], cycle_id: str | None = None, model_override=None, max_candidates: int = 3) -> list[IdeaBookEntry]:
        if not metrics:
            return []
        universe = self.runtime_context.hedge_fund_profile.get("universe") or {}
        tickers = [ticker for ticker in universe if metrics.get(ticker)]
        if not tickers:
            return []
        existing_entries = self.list_entries()
        existing_keys = {
            self._idea_fingerprint(entry.ticker, entry.side, entry.thesis)
            for entry in existing_entries
        }
        model = model_override or self._build_generation_model()
        agent = Agent(
            model=model,
            output_type=IdeaGenerationResponse,
            instructions=(
                "You are an idea generation analyst for a long/short equity hedge fund. "
                "Return only ideas that express a clear market mispricing, explicit catalyst, timing, invalidation rule, "
                "and concise evidence. Reject vague narratives. Use only the provided profile and market metrics. "
                "Do not duplicate an existing ticker/side/thesis combination. "
                "Default new ideas to candidate quality; do not assume they are investable yet."
            ),
            defer_model_check=True,
        )
        prompt = self._build_generation_prompt(
            metrics=metrics,
            tickers=tickers,
            existing_entries=existing_entries,
            max_candidates=max_candidates,
            runtime_context=self.runtime_context,
        )
        try:
            result = self._run_generation(agent, prompt)
            generated = result.output.ideas
        except Exception:
            return []

        persisted: list[dict] = []
        for candidate in generated:
            fingerprint = self._idea_fingerprint(candidate.ticker, candidate.side, candidate.thesis)
            if fingerprint in existing_keys:
                continue
            existing_keys.add(fingerprint)
            persisted.append({
                "idea_id": self._build_idea_id(candidate.ticker, candidate.side),
                "ticker": candidate.ticker,
                "side": candidate.side,
                "thesis": candidate.thesis,
                "catalyst": candidate.catalyst,
                "time_horizon": candidate.time_horizon,
                "conviction": candidate.conviction,
                "upside_case": candidate.upside_case,
                "downside_case": candidate.downside_case,
                "invalidation_rule": candidate.invalidation_rule,
                "status": "candidate",
                "sleeve": candidate.sleeve,
                "edge_source": candidate.edge_source,
                "why_now": candidate.why_now,
                "key_risk": candidate.key_risk,
                "supporting_signals": candidate.supporting_signals,
                "evidence_quality": candidate.evidence_quality,
                "review_status": "pending_review",
                "origin_cycle_id": cycle_id,
                "llm_generated": True,
                "source": "llm_generation",
                "crowded_score": float((universe.get(candidate.ticker) or {}).get("crowded_score", 0.0)),
                "short_squeeze_risk": bool((universe.get(candidate.ticker) or {}).get("short_squeeze_risk", False)),
            })
        if not persisted:
            return []
        upsert_idea_book(persisted, db_path=self.db_path)
        return [IdeaBookEntry(**entry) for entry in get_idea_book(review_status="pending_review", llm_generated=True, db_path=self.db_path)]

    def review_entry(self, idea_id: str, review_status: str) -> bool:
        return update_idea_book_entry(idea_id, review_status=review_status, db_path=self.db_path)

    def promote_entry(self, idea_id: str, status: str) -> bool:
        return update_idea_book_entry(idea_id, status=status, review_status="approved", db_path=self.db_path)

    @staticmethod
    def _build_generation_model():
        from agents.portfolio_agent import build_agent_model

        return build_agent_model()

    @staticmethod
    def _idea_fingerprint(ticker: str, side: str, thesis: str) -> str:
        normalized = f"{ticker.strip().upper()}|{side.strip().lower()}|{' '.join(thesis.lower().split())}"
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_idea_id(ticker: str, side: str) -> str:
        return f"idea-{ticker.lower()}-{side.lower()}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _build_generation_prompt(
        *,
        metrics: dict[str, dict],
        tickers: list[str],
        existing_entries: list[IdeaBookEntry],
        max_candidates: int,
        runtime_context,
    ) -> str:
        profile = {
            "default_time_horizon": runtime_context.hedge_fund_profile.get("default_time_horizon"),
            "sleeves": runtime_context.hedge_fund_profile.get("sleeves") or {},
            "universe": {ticker: (runtime_context.hedge_fund_profile.get("universe") or {}).get(ticker, {}) for ticker in tickers},
        }
        existing = [
            {
                "ticker": entry.ticker,
                "side": entry.side,
                "thesis": entry.thesis,
                "status": entry.status,
                "review_status": entry.review_status,
            }
            for entry in existing_entries
        ]
        context = {
            "max_candidates": max_candidates,
            "profile": profile,
            "metrics": {ticker: metrics.get(ticker, {}) for ticker in tickers},
            "existing_ideas": existing,
            "requirements": [
                "Each idea must include an explicit source of edge.",
                "Each idea must explain why now and what catalyzes price discovery.",
                "Each idea must include one primary risk and one invalidation rule.",
                "Keep supporting_signals concise and evidence-based.",
                "Prefer diversified output across the provided universe.",
            ],
        }
        return (
            "Generate up to the requested number of new hedge fund idea candidates.\n"
            "Use the context below as the only source of truth.\n"
            f"{json.dumps(context, ensure_ascii=True)}"
        )

    @staticmethod
    def _run_generation(agent: Agent, prompt: str):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return agent.run_sync(prompt)

        result: dict[str, object] = {}
        error: list[BaseException] = []

        def _runner() -> None:
            try:
                result["value"] = agent.run_sync(prompt)
            except BaseException as exc:
                error.append(exc)

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()
        if error:
            raise error[0]
        return result["value"]
