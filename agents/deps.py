"""Dependencies and adapters injected into the Pydantic AI agent."""

from __future__ import annotations

from dataclasses import dataclass, field

from services.gateways import AuditRepository, ExecutionGateway, MarketDataGateway, PortfolioRepository


@dataclass
class AgentDependencies:
    market_gateway: MarketDataGateway
    portfolio_repository: PortfolioRepository
    execution_gateway: ExecutionGateway
    audit_repository: AuditRepository
    strategy_name: str
    execution_mode: str
    active_trade_plan: list[dict] = field(default_factory=list)
    cycle_id: str = ""
