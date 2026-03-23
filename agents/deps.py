"""Dependencies and adapters injected into the Pydantic AI agent."""

from __future__ import annotations

from dataclasses import dataclass, field

from services.gateways import AuditRepository, ExecutionGateway, MarketDataGateway, PortfolioRepository, ResearchGateway


@dataclass
class AgentDependencies:
    market_gateway: MarketDataGateway
    portfolio_repository: PortfolioRepository
    execution_gateway: ExecutionGateway
    research_gateway: ResearchGateway
    audit_repository: AuditRepository
    strategy_name: str
    execution_mode: str
    mcp_profile: str = "none"
    capability_registry: object | None = None
    active_trade_plan: list[dict] = field(default_factory=list)
    cycle_id: str = ""
