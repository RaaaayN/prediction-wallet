"""Strategy registry and factory helpers."""

from __future__ import annotations

from config import CALENDAR_FREQUENCY, DRIFT_THRESHOLD
from strategies.calendar import CalendarStrategy
from strategies.threshold import ThresholdStrategy
from strategies.ensemble import EnsembleStrategy
from strategies.predictive_ml import PredictiveMLStrategy


STRATEGY_REGISTRY = {
    "threshold": ThresholdStrategy,
    "calendar": CalendarStrategy,
    "ensemble": EnsembleStrategy,
    "predictive_ml": PredictiveMLStrategy,
}


def available_strategy_names() -> list[str]:
    return sorted(STRATEGY_REGISTRY)


def build_strategy(strategy_name: str, profile: dict | None = None):
    profile = profile or {}
    try:
        strategy_cls = STRATEGY_REGISTRY[strategy_name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. Available strategies: {', '.join(available_strategy_names())}"
        ) from exc

    if strategy_cls is ThresholdStrategy:
        return strategy_cls(
            threshold=float(profile.get("drift_threshold", DRIFT_THRESHOLD)),
            target_allocation=profile.get("target_allocation"),
            per_asset_threshold=dict(profile.get("per_asset_threshold") or {}),
        )

    if strategy_cls is CalendarStrategy:
        return strategy_cls(
            frequency=str(profile.get("calendar_frequency", CALENDAR_FREQUENCY)),
            target_allocation=profile.get("target_allocation"),
            min_drift=float(profile.get("drift_threshold", 0.01)),
        )

    if strategy_cls is EnsembleStrategy:
        return strategy_cls(
            target_allocation=profile.get("target_allocation", {}),
            drift_threshold=float(profile.get("drift_threshold", DRIFT_THRESHOLD)),
            sentiment_weight=float(profile.get("sentiment_weight", 0.2)),
        )

    if strategy_cls is PredictiveMLStrategy:
        return strategy_cls(
            target_allocation=profile.get("target_allocation"),
            model_run_id=profile.get("ml_model_run_id"),
        )

    raise ValueError(f"Unsupported strategy class for '{strategy_name}'")
