"""Runtime profile context and profile-scoped storage resolution."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from portfolio_loader import get_active_profile, load_profile
from settings import settings
from utils.time import utc_now_iso


DEFAULT_ACTIVE_PROFILE = "balanced"
DEFAULT_SECTOR_MAP: dict[str, str] = {
    "AAPL": "tech",
    "MSFT": "tech",
    "GOOGL": "tech",
    "AMZN": "tech",
    "NVDA": "tech",
    "TLT": "bonds",
    "BND": "bonds",
    "BTC-USD": "crypto",
    "ETH-USD": "crypto",
}


@dataclass(frozen=True)
class RuntimeProfileContext:
    profile_name: str
    profile: dict
    data_dir: str
    profile_dir: str
    portfolio_file: str
    trades_log: str
    market_db: str
    reports_dir: str
    target_allocation: dict[str, float]
    initial_capital: float
    drift_threshold: float
    kill_switch_drawdown: float
    slippage_equities: float
    slippage_crypto: float
    hedge_fund_profile: dict
    policy: dict
    per_asset_threshold: dict[str, float]
    vol_blend: float
    sector_map: dict[str, str]
    crypto_tickers: set[str]

    @property
    def allowed_tickers(self) -> list[str]:
        return list(self.target_allocation.keys())


def _data_root() -> Path:
    return Path(settings.data_dir)


def _runtime_state_path() -> Path:
    return _data_root() / "active_profile.json"


def _profiles_root() -> Path:
    return _data_root() / "profiles"


def _legacy_root() -> Path:
    return _data_root() / "legacy"


def list_available_profiles() -> list[str]:
    profiles_dir = Path(__file__).parent / "profiles"
    return sorted(path.stem for path in profiles_dir.glob("*.yaml"))


def get_active_profile_name() -> str:
    state_path = _runtime_state_path()
    if state_path.exists():
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            profile_name = str(payload.get("profile_name") or "").strip()
            if profile_name:
                load_profile(profile_name)
                return profile_name
        except Exception:
            pass

    env_name = os.getenv("PORTFOLIO_PROFILE")
    if env_name:
        try:
            load_profile(env_name)
            return env_name
        except Exception:
            pass

    try:
        return get_active_profile().get("name", DEFAULT_ACTIVE_PROFILE)
    except Exception:
        return DEFAULT_ACTIVE_PROFILE


def set_active_profile_name(profile_name: str) -> str:
    profile = load_profile(profile_name)
    state_path = _runtime_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "profile_name": profile["name"],
                "updated_at": utc_now_iso(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    os.environ["PORTFOLIO_PROFILE"] = profile["name"]
    return profile["name"]


def build_default_portfolio(initial_capital: float) -> dict:
    return {
        "positions": {},
        "position_sides": {},
        "average_costs": {},
        "position_ideas": {},
        "cash": initial_capital,
        "peak_value": initial_capital,
        "last_rebalanced": None,
        "history": [],
        "created_at": utc_now_iso(),
    }


def build_runtime_context(profile_name: str | None = None, *, ensure_storage: bool = True) -> RuntimeProfileContext:
    resolved_name = profile_name or get_active_profile_name()
    profile = load_profile(resolved_name)
    profile_dir = _profiles_root() / resolved_name
    target_allocation = dict(profile.get("target_allocation") or {})
    hedge_fund_profile = dict(profile.get("hedge_fund") or {})
    sector_map = dict(DEFAULT_SECTOR_MAP)
    for ticker, meta in (hedge_fund_profile.get("universe") or {}).items():
        sector = (meta or {}).get("sector")
        if sector:
            sector_map[ticker] = str(sector)
    context = RuntimeProfileContext(
        profile_name=resolved_name,
        profile=profile,
        data_dir=str(_data_root()),
        profile_dir=str(profile_dir),
        portfolio_file=str(profile_dir / "portfolio.json"),
        trades_log=str(profile_dir / "trades.log"),
        market_db=str(profile_dir / "market.db"),
        reports_dir=str(profile_dir / "reports"),
        target_allocation=target_allocation,
        initial_capital=float(profile["initial_capital"]),
        drift_threshold=float(profile["drift_threshold"]),
        kill_switch_drawdown=float(profile["kill_switch_drawdown"]),
        slippage_equities=float(profile["slippage_equities"]),
        slippage_crypto=float(profile["slippage_crypto"]),
        hedge_fund_profile=hedge_fund_profile,
        policy=dict(profile.get("policy") or {}),
        per_asset_threshold=dict(profile.get("per_asset_threshold") or {}),
        vol_blend=float(profile.get("vol_blend", 0.3)),
        sector_map=sector_map,
        crypto_tickers={ticker for ticker in target_allocation if "USD" in ticker and "-" in ticker},
    )
    if ensure_storage:
        ensure_profile_storage(context)
    return context


def ensure_profile_storage(context: RuntimeProfileContext) -> None:
    profile_dir = Path(context.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    Path(context.reports_dir).mkdir(parents=True, exist_ok=True)
    portfolio_path = Path(context.portfolio_file)
    if not portfolio_path.exists():
        portfolio_path.write_text(
            json.dumps(build_default_portfolio(context.initial_capital), indent=2),
            encoding="utf-8",
        )


def backup_legacy_state() -> Path | None:
    data_root = _data_root()
    legacy_targets = [
        data_root / "portfolio.json",
        data_root / "trades.log",
        data_root / "market.db",
        data_root / "reports",
    ]
    existing = [path for path in legacy_targets if path.exists()]
    if not existing:
        return None
    backup_dir = _legacy_root() / utc_now_iso().replace(":", "-")
    backup_dir.mkdir(parents=True, exist_ok=True)
    for source in existing:
        destination = backup_dir / source.name
        shutil.move(str(source), str(destination))
    return backup_dir


def reset_profile_market_cache(context: RuntimeProfileContext) -> None:
    market_db = Path(context.market_db)
    if market_db.exists():
        backup_dir = Path(context.profile_dir) / "cache_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_name = f"market_{utc_now_iso().replace(':', '-')}.db"
        shutil.move(str(market_db), str(backup_dir / backup_name))
