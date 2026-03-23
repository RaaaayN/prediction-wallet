"""Compatibility wrapper around the new Pydantic AI cycle service."""

from agents.portfolio_agent import PortfolioAgentService


class _CompatGraph:
    def __init__(self):
        self._service = PortfolioAgentService()

    def invoke(self, initial_state: dict) -> dict:
        return self._service.run_cycle_dict(
            strategy_name=initial_state.get("strategy_name", "threshold"),
            execution_mode=initial_state.get("execution_mode", "simulate"),
            mcp_profile=initial_state.get("mcp_profile", "none"),
        )


graph = _CompatGraph()
