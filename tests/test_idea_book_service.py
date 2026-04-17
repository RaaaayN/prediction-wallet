import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

from api.main import app
from db.schema import init_db
from services.idea_book_service import IdeaBookService


TEST_HEDGE_FUND_PROFILE: dict = {
    "default_time_horizon": "1-3 months",
    "sleeves": {
        "core_longs": {"max_gross": 1.0},
        "shorts": {"max_gross": 0.6},
    },
    "universe": {
        "AAPL": {"crowded_score": 0.2, "short_squeeze_risk": False},
        "MSFT": {"crowded_score": 0.1, "short_squeeze_risk": False},
        "GOOGL": {"crowded_score": 0.3, "short_squeeze_risk": False},
    },
    "ideas": [
        {
            "idea_id": "seed-aapl",
            "ticker": "AAPL",
            "side": "long",
            "thesis": "Resilient cash flow compounder",
            "catalyst": "Services growth",
            "time_horizon": "3-6 months",
            "conviction": 0.72,
            "upside_case": "Re-rating",
            "downside_case": "Hardware slowdown",
            "invalidation_rule": "Services growth slows sharply",
            "status": "investable",
            "sleeve": "core_longs",
        }
    ],
}


def _test_runtime_context(db_path: str) -> SimpleNamespace:
    """Minimal runtime context for unit tests (replaces module-level HEDGE_FUND_PROFILE)."""
    return SimpleNamespace(
        hedge_fund_profile=TEST_HEDGE_FUND_PROFILE,
        market_db=str(db_path),
        target_allocation={},
        sector_map={},
        profile_name="test",
    )


def _candidate_output(ticker: str = "MSFT") -> dict:
    return {
        "ideas": [
            {
                "ticker": ticker,
                "side": "long",
                "thesis": "AI monetization is still underappreciated by consensus",
                "catalyst": "Upcoming cloud and AI revenue commentary",
                "time_horizon": "1-3 months",
                "conviction": 0.66,
                "upside_case": "Estimate revisions drive multiple expansion",
                "downside_case": "Enterprise demand softens",
                "invalidation_rule": "Commercial bookings fail to inflect over two quarters",
                "sleeve": "core_longs",
                "edge_source": "fundamental",
                "why_now": "Near-term updates can force estimate revisions",
                "key_risk": "AI demand monetization remains slower than priced into the thesis",
                "supporting_signals": ["Stable margins", "Recurring enterprise demand"],
                "evidence_quality": "medium",
            }
        ]
    }


def test_generate_candidates_persists_pending_review(monkeypatch, tmp_path):
    db_path = tmp_path / "ideas.db"
    init_db(str(db_path))

    service = IdeaBookService(db_path=str(db_path), runtime_context=_test_runtime_context(str(db_path)))
    service.seed_from_profile()
    generated = service.generate_candidates(
        metrics={
            "AAPL": {"last_price": 100.0, "volatility_30d": 0.2, "ytd_return": 0.1, "sharpe": 1.1},
            "MSFT": {"last_price": 100.0, "volatility_30d": 0.18, "ytd_return": 0.12, "sharpe": 1.2},
        },
        cycle_id="cycle-123",
        model_override=TestModel(custom_output_args=_candidate_output()),
    )

    assert len(generated) == 1
    idea = next(entry for entry in service.list_entries() if entry.ticker == "MSFT")
    assert idea.status == "candidate"
    assert idea.review_status == "pending_review"
    assert idea.llm_generated is True
    assert idea.origin_cycle_id == "cycle-123"


def test_generate_candidates_deduplicates_repeated_runs(monkeypatch, tmp_path):
    db_path = tmp_path / "ideas.db"
    init_db(str(db_path))

    service = IdeaBookService(db_path=str(db_path), runtime_context=_test_runtime_context(str(db_path)))
    service.seed_from_profile()
    model = TestModel(custom_output_args=_candidate_output())
    metrics = {
        "MSFT": {"last_price": 100.0, "volatility_30d": 0.18, "ytd_return": 0.12, "sharpe": 1.2},
        "AAPL": {"last_price": 100.0, "volatility_30d": 0.2, "ytd_return": 0.1, "sharpe": 1.1},
    }

    first = service.generate_candidates(metrics=metrics, model_override=model)
    second = service.generate_candidates(metrics=metrics, model_override=model)

    assert len(first) == 1
    assert second == []
    msft_entries = [entry for entry in service.list_entries() if entry.ticker == "MSFT"]
    assert len(msft_entries) == 1


def test_research_only_uses_approved_non_candidate_ideas(monkeypatch, tmp_path):
    db_path = tmp_path / "ideas.db"
    init_db(str(db_path))

    service = IdeaBookService(db_path=str(db_path), runtime_context=_test_runtime_context(str(db_path)))
    service.seed_from_profile()
    service.generate_candidates(
        metrics={
            "MSFT": {"last_price": 100.0, "volatility_30d": 0.18, "ytd_return": 0.12, "sharpe": 1.2},
            "AAPL": {"last_price": 100.0, "volatility_30d": 0.2, "ytd_return": 0.1, "sharpe": 1.1},
        },
        model_override=TestModel(custom_output_args=_candidate_output()),
    )
    pending_research = service.research({
        "AAPL": {"last_price": 100.0, "volatility_30d": 0.2, "ytd_return": 0.1, "sharpe": 1.1},
        "MSFT": {"last_price": 100.0, "volatility_30d": 0.18, "ytd_return": 0.12, "sharpe": 1.2},
    })
    assert {idea.ticker for idea in pending_research} == {"AAPL"}

    msft_idea = next(entry for entry in service.list_entries() if entry.ticker == "MSFT")
    assert service.review_entry(msft_idea.idea_id, "approved") is True
    assert service.promote_entry(msft_idea.idea_id, "investable") is True

    approved_research = service.research({
        "AAPL": {"last_price": 100.0, "volatility_30d": 0.2, "ytd_return": 0.1, "sharpe": 1.1},
        "MSFT": {"last_price": 100.0, "volatility_30d": 0.18, "ytd_return": 0.12, "sharpe": 1.2},
    })
    assert {idea.ticker for idea in approved_research} == {"AAPL", "MSFT"}


def test_idea_book_api_generation_review_and_promote(monkeypatch, tmp_path):
    db_path = tmp_path / "ideas.db"
    portfolio_path = tmp_path / "portfolio.json"
    init_db(str(db_path))
    portfolio_path.write_text(json.dumps({"positions": {}, "cash": 100000.0, "peak_value": 100000.0, "history": []}), encoding="utf-8")

    import api.main as api_main
    import config as config_module
    import db.repository as repository_module
    import services.idea_book_service as idea_book_module
    import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "market_db", str(db_path))
    monkeypatch.setattr(settings_module.settings, "portfolio_file", str(portfolio_path))
    monkeypatch.setattr(config_module, "MARKET_DB", str(db_path))
    monkeypatch.setattr(config_module, "PORTFOLIO_FILE", str(portfolio_path))
    monkeypatch.setattr(config_module, "HEDGE_FUND_PROFILE", TEST_HEDGE_FUND_PROFILE)
    monkeypatch.setattr(repository_module, "MARKET_DB", str(db_path))
    monkeypatch.setattr(
        idea_book_module,
        "build_runtime_context",
        lambda *_a, **_k: _test_runtime_context(str(db_path)),
    )
    monkeypatch.setattr(api_main, "_load_idea_metrics", lambda: {
        "AAPL": {"last_price": 100.0, "volatility_30d": 0.2, "ytd_return": 0.1, "sharpe": 1.1},
        "MSFT": {"last_price": 100.0, "volatility_30d": 0.18, "ytd_return": 0.12, "sharpe": 1.2},
    })
    monkeypatch.setattr(
        idea_book_module.IdeaBookService,
        "_build_generation_model",
        staticmethod(lambda: TestModel(custom_output_args=_candidate_output())),
    )

    client = TestClient(app)

    generated = client.post("/api/idea-book/generate", json={"cycle_id": "cycle-api", "max_candidates": 2})
    assert generated.status_code == 200
    pending = generated.json()
    assert len(pending) == 1
    idea_id = pending[0]["idea_id"]

    filtered = client.get("/api/idea-book", params={"review_status": "pending_review", "llm_generated": True})
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1

    review = client.post(f"/api/idea-book/{idea_id}/review", json={"review_status": "approved"})
    assert review.status_code == 200
    promote = client.post(f"/api/idea-book/{idea_id}/promote", json={"status": "watchlist"})
    assert promote.status_code == 200

    live = client.get("/api/idea-book", params={"review_status": "approved"})
    assert live.status_code == 200
    promoted = next(entry for entry in live.json() if entry["idea_id"] == idea_id)
    assert promoted["status"] == "watchlist"
    assert promoted["review_status"] == "approved"
