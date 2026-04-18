# Trading Core v1

The Trading Core is a deterministic, persistent, and auditable Order Management System (OMS) and Portfolio Management System (PMS) layer for the `prediction-wallet`.

## Architecture

The Trading Core has been industrialized into a persistent service-oriented architecture:

1.  **TradingCoreService**: The central orchestrator that manages the lifecycle of trades, ensuring transactional integrity between the OMS, Ledger, and Database.
2.  **Security Master**: Canonical repository of tradable instruments. It now automatically persists new instruments to the database and reloads state on startup.
3.  **Market Data Handler**: Adapts raw market data into canonical `MarketPrice` objects with freshness tracking and persistence of snapshots.
4.  **Order Management System (OMS)**: Manages order lifecycle. Every state transition is recorded in the `orders` and `order_events` tables for a complete audit trail.
5.  **Broker Adapters**: Interfaces for trade execution. Currently includes a `SimulationBrokerAdapter` with slippage models.
6.  **Ledger**: The source of truth for aggregate positions and cash movements. It is fully backed by the `position_ledger` and `cash_movements` tables.

## Persistence

Unlike previous versions that relied on in-memory state or manual repository calls, the Trading Core components now handle their own persistence:
- **Instruments** are upserted as they are discovered or bootstrapped.
- **Orders** and their status updates are saved immediately.
- **Executions** are recorded in the `trade_executions_v2` table.
- **Positions** and **Cash** are updated in the database atomically as part of the execution application process.

## Integration

The Trading Core is encapsulated within the `TradingCoreService`. The `PortfolioAgentService` utilizes this service to execute its trade plan when `TRADING_CORE_ENABLED=true`.

## Configuration

Enable the Trading Core via environment variable:
```bash
TRADING_CORE_ENABLED=true
```

## API Endpoints

Industrialized endpoints for inspecting the Trading Core state:
- `GET /api/trading-core/instruments`: List known instruments.
- `GET /api/trading-core/positions`: Active ledger positions (from DB).
- `GET /api/trading-core/orders`: Order history (from DB).
- `GET /api/trading-core/executions`: Execution history (from DB).
- `GET /api/trading-core/cash-movements`: Cash history (from DB).
