"""Security Master for instrument bootstrapping and management."""

from __future__ import annotations
from typing import Dict, List, Set
from trading_core.models import Instrument, InstrumentType
from config import TARGET_ALLOCATION, HEDGE_FUND_PROFILE, SECTOR_MAP
import json

class SecurityMaster:
    """Manages the universe of known instruments."""

    def __init__(self):
        self._instruments: Dict[str, Instrument] = {}

    @staticmethod
    def make_instrument_id(symbol: str, asset_class: InstrumentType) -> str:
        """Generate a stable, deterministic instrument ID."""
        return f"{asset_class.value.upper()}:{symbol.upper()}"

    def bootstrap(self, existing_positions: Dict[str, float] = None):
        """Seed the security master from config and existing data."""
        # 1. Target Allocation
        for ticker in TARGET_ALLOCATION:
            self._add_ticker(ticker)

        # 2. Hedge Fund Universe
        universe = HEDGE_FUND_PROFILE.get("universe", {})
        for ticker in universe:
            self._add_ticker(ticker)

        # 3. Existing Positions
        if existing_positions:
            for ticker in existing_positions:
                self._add_ticker(ticker)

    def _add_ticker(self, ticker: str):
        asset_class = InstrumentType.EQUITY
        if "USD" in ticker and "-" in ticker:
            asset_class = InstrumentType.CRYPTO
        
        instrument_id = self.make_instrument_id(ticker, asset_class)
        if instrument_id in self._instruments:
            return

        name = ticker
        sector = SECTOR_MAP.get(ticker)
        
        # Try to find more metadata from HEDGE_FUND_PROFILE
        universe_meta = HEDGE_FUND_PROFILE.get("universe", {}).get(ticker, {})
        if universe_meta:
            name = universe_meta.get("name", name)
            sector = universe_meta.get("sector", sector)

        self._instruments[instrument_id] = Instrument(
            instrument_id=instrument_id,
            symbol=ticker,
            name=name,
            asset_class=asset_class,
            sector=sector,
            metadata_json=universe_meta if isinstance(universe_meta, dict) else {}
        )

    def get_instrument(self, instrument_id: str) -> Instrument | None:
        return self._instruments.get(instrument_id)

    def get_by_symbol(self, symbol: str) -> Instrument | None:
        for inst in self._instruments.values():
            if inst.symbol == symbol:
                return inst
        return None

    def list_instruments(self) -> List[Instrument]:
        return list(self._instruments.values())

    def get_or_create_by_symbol(self, symbol: str) -> Instrument:
        inst = self.get_by_symbol(symbol)
        if inst:
            return inst
        self._add_ticker(symbol)
        return self.get_by_symbol(symbol)  # type: ignore
