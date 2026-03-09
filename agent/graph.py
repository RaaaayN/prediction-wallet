"""LangGraph state machine for the portfolio rebalancing agent."""

from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes import (
    observe_node,
    analyze_node,
    decide_node,
    execute_node,
    audit_node,
    alert_node,
)


def _route_after_execute(state: AgentState) -> str:
    """Route to alert if kill switch is active, otherwise to audit."""
    if state.get("kill_switch_active"):
        return "alert"
    return "audit"


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph rebalancing agent."""
    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("observe", observe_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("decide", decide_node)
    builder.add_node("execute", execute_node)
    builder.add_node("audit", audit_node)
    builder.add_node("alert", alert_node)

    # Linear edges
    builder.set_entry_point("observe")
    builder.add_edge("observe", "analyze")
    builder.add_edge("analyze", "decide")
    builder.add_edge("decide", "execute")

    # Conditional: kill switch check after execute
    builder.add_conditional_edges(
        "execute",
        _route_after_execute,
        {"alert": "alert", "audit": "audit"},
    )

    builder.add_edge("alert", END)
    builder.add_edge("audit", END)

    return builder.compile()


# Singleton compiled graph
graph = build_graph()
