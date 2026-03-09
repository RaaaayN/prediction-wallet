"""Pure risk computation functions — no I/O, no LLM."""

from __future__ import annotations


def compute_drawdown(current_value: float, peak_value: float) -> float:
    """Compute drawdown of current value from peak (negative number).

    Returns:
        Drawdown as a fraction, e.g. -0.15 means -15%
    """
    if peak_value <= 0:
        return 0.0
    return (current_value - peak_value) / peak_value


def check_kill_switch(drawdown: float, threshold: float) -> bool:
    """Return True if drawdown exceeds the threshold and trading should halt.

    Args:
        drawdown: current drawdown (negative fraction, e.g. -0.12)
        threshold: positive threshold value (e.g. 0.10 for 10%)

    Returns:
        True if abs(drawdown) > threshold (kill switch should activate)
    """
    return drawdown < -threshold
