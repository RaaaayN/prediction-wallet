"""Compatibility layer for the legacy node API."""

from agents.portfolio_agent import PortfolioAgentService

_service = PortfolioAgentService()


def observe_node(state):
    return _service.observe(
        strategy_name=state.get("strategy_name", "threshold"),
        execution_mode=state.get("execution_mode", "simulate"),
        mcp_profile=state.get("mcp_profile", "none"),
        cycle_id=state.get("cycle_id"),
    ).model_dump()


def analyze_node(state):
    observation = _service.observe(
        strategy_name=state.get("strategy_name", "threshold"),
        execution_mode=state.get("execution_mode", "simulate"),
        mcp_profile=state.get("mcp_profile", "none"),
        cycle_id=state.get("cycle_id"),
    )
    decision, stats = _service.decide(observation, execution_mode=state.get("execution_mode", "simulate"), mcp_profile=state.get("mcp_profile", "none"))
    payload = observation.model_dump()
    payload["analysis"] = decision.rationale
    payload["decision"] = decision.model_dump()
    payload["observability"] = stats
    return payload


def decide_node(state):
    return state


def execute_node(state):
    return state


def audit_node(state):
    return state


def alert_node(state):
    return state
