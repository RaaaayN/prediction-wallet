"""Compatibility exports for legacy tests and integrations."""

from agents.portfolio_agent import PortfolioAgentService
from agents.portfolio_agent import build_portfolio_agent as build_tool_runtime


class ToolRuntime:
    """Legacy placeholder kept for backward compatibility."""

    def __init__(self, runtime=None):
        self.runtime = runtime

    def set_state(self, state: dict) -> None:
        self.state = state

    def dispatch_tool(self, tool_name: str, tool_input: dict) -> str:
        raise RuntimeError("Legacy ToolRuntime has been replaced by the Pydantic AI agent.")
