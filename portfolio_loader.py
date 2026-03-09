"""Load a portfolio profile from a YAML file in profiles/."""

from __future__ import annotations

import os
from pathlib import Path

_PROFILES_DIR = Path(__file__).parent / "profiles"
_VALID_PROFILES = {"balanced", "conservative", "growth", "crypto_heavy"}


def load_profile(name: str) -> dict:
    """Load and return a portfolio profile by name.

    Args:
        name: profile name — one of balanced, conservative, growth, crypto_heavy

    Returns:
        Dict with keys: name, description, initial_capital, target_allocation,
        drift_threshold, kill_switch_drawdown, slippage_equities, slippage_crypto

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
    """Load the profile specified by the PORTFOLIO_PROFILE env var (default: balanced)."""
    name = os.getenv("PORTFOLIO_PROFILE", "balanced")
    return load_profile(name)


def _validate(data: dict, name: str) -> None:
    """Raise ValueError if the profile dict is missing required keys or allocation is wrong."""
    required = {"name", "initial_capital", "target_allocation", "drift_threshold",
                "kill_switch_drawdown", "slippage_equities", "slippage_crypto"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Profile '{name}' is missing keys: {missing}")

    total = sum(data["target_allocation"].values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(
            f"Profile '{name}' target_allocation sums to {total:.6f}, expected 1.0"
        )
