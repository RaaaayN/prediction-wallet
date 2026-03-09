"""LangGraph agent state definition."""

from typing import TypedDict, Annotated
import operator


class AgentState(TypedDict):
    portfolio: dict                      # positions, cash, history, peak_value
    market_data: dict                    # prices, metrics per ticker
    strategy_signal: bool                # did strategy trigger rebalancing?
    analysis: str                        # LLM market analysis text
    trades_pending: list                 # trades proposed (not yet executed)
    trades_executed: list                # confirmed executed trades
    report_path: str | None              # path to generated PDF
    kill_switch_active: bool             # emergency stop flag
    cycle_id: str                        # UUID for this agent cycle
    messages: Annotated[list, operator.add]  # LangGraph message accumulator
    strategy_name: str                   # "threshold" or "calendar"
    errors: list                         # non-fatal errors collected during cycle
