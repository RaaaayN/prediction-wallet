# Trading Core v1

The Trading Core is a deterministic and auditable Order Management System (OMS) and Portfolio Management System (PMS) layer for the `prediction-wallet`.

## Architecture

The Trading Core introduces formal objects and processes for the trading lifecycle:

1.  **Security Master**: Canonical repository of tradable instruments with stable `instrument_id`.
2.  **Market Data Handler**: Adapts raw market data into canonical `MarketPrice` objects with freshness tracking.
3.  **Order Management System (OMS)**: Manages order creation, validation, and state transitions (`CREATED` -> `VALIDATED` -> `SUBMITTED` -> `FILLED`).
4.  **Broker Adapters**: Interfaces for trade execution. Currently includes a `SimulationBrokerAdapter` that applies slippage models.
5.  **Ledger**: The source of truth for aggregate positions and cash movements.

## Data Models

- **Instrument**: `EQUITY:AAPL`, `CRYPTO:BTC-USD`, etc.
- **Order**: Represents an intent to trade.
- **Execution**: Represents a fulfilled trade.
- **Position**: Aggregate holding of an instrument.
- **CashMovement**: Atomic update to the cash balance (trade, fee, dividend, etc.).

## Integration

The Trading Core is integrated into the `PortfolioAgentService.execute()` cycle. When `TRADING_CORE_ENABLED=true`, every trade goes through the formal OMS and Ledger process before being synced back to the legacy state for backward compatibility.

## Configuration

Enable the Trading Core via environment variable:
```bash
TRADING_CORE_ENABLED=true
```

## API Endpoints

New endpoints are available for inspecting the Trading Core state:
- `GET /api/trading-core/instruments`: List known instruments.
- `GET /api/trading-core/positions`: Active ledger positions.
- `GET /api/trading-core/orders`: Order history.
- `GET /api/trading-core/executions`: Execution history.
- `GET /api/trading-core/cash-movements`: Cash history.
