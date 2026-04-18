"""Load a portfolio profile from a YAML file in profiles/."""

from __future__ import annotations

import os
from pathlib import Path

_PROFILES_DIR = Path(__file__).parent / "profiles"
_VALID_PROFILES = {"balanced", "conservative", "growth", "crypto_heavy", "long_short_equity"}


def load_profile(name: str) -> dict:
    """Load and return a portfolio profile by name.

    Args:
        name: profile name — one of balanced, conservative, growth, crypto_heavy, long_short_equity

    Returns:
        Dict with keys: name, description, initial_capital and strategy-specific
        configuration. Long-only profiles require target_allocation. Hedge-fund
        profiles may additionally declare hedge_fund settings and an idea_book.

    Raises:
        ValueError: if the profile name is unknown or the file is invalid
    """
    if name not in _VALID_PROFILES:
        raise ValueError(f"Unknown profile '{name}'. Valid options: {sorted(_VALID_PROFILES)}")

    path = _PROFILES_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Profile file not found: {path}")

    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required. Install it with: pip install pyyaml")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    _validate(data, name)
    return data


def get_active_profile() -> dict:
    """Load the profile specified by settings (default: balanced)."""
    from settings import settings
    profile_name = os.getenv("PORTFOLIO_PROFILE") or settings.portfolio_profile
    return load_profile(profile_name)


def _validate(data: dict, name: str) -> None:
    """Raise ValueError if the profile dict is missing required keys or allocation is wrong."""
    required = {"name", "initial_capital", "drift_threshold",
                "kill_switch_drawdown", "slippage_equities", "slippage_crypto"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Profile '{name}' is missing keys: {missing}")

    target_allocation = data.get("target_allocation")
    hedge_fund = data.get("hedge_fund") or {}
    if target_allocation is None:
        universe = hedge_fund.get("universe") or {}
        if universe:
            data["target_allocation"] = {ticker: 0.0 for ticker in universe}
        else:
            raise ValueError(
                f"Profile '{name}' must define target_allocation or hedge_fund.universe"
            )

    total = sum(data["target_allocation"].values())
    if total > 0 and abs(total - 1.0) > 1e-6:
        raise ValueError(
            f"Profile '{name}' target_allocation sums to {total:.6f}, expected 1.0"
        )
