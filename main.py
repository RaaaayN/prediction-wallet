"""CLI entry point for the autonomous portfolio rebalancing agent."""

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta

from config import TARGET_ALLOCATION, ANTHROPIC_API_KEY, GEMINI_API_KEY, AI_PROVIDER


def check_api_key():
    if AI_PROVIDER == "gemini":
        if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("AIza..."):
            print("ERROR: GEMINI_API_KEY not set. Ajoutez-la dans votre fichier .env.")
            sys.exit(1)
    else:
        if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.startswith("sk-ant-..."):
            print("ERROR: ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key.")
            sys.exit(1)


def run_agent_cycle(strategy: str = "threshold") -> dict:
    """Run a single agent cycle and return the final state."""
    from agent.graph import graph

    initial_state = {
        "portfolio": {},
        "market_data": {},
        "strategy_signal": False,
        "analysis": "",
        "trades_pending": [],
        "trades_executed": [],
        "report_path": None,
        "kill_switch_active": False,
        "cycle_id": str(uuid.uuid4())[:8],
        "messages": [],
        "strategy_name": strategy,
        "errors": [],
    }

    print(f"\n{'='*60}")
    print(f"  Prediction Wallet — Rebalancing Agent")
    print(f"  Strategy: {strategy} | Cycle: {initial_state['cycle_id']}")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    final_state = graph.invoke(initial_state)

    print(f"\n{'='*60}")
    print(f"  Cycle complete.")
    print(f"  Trades executed: {len(final_state.get('trades_executed', []))}")
    print(f"  Kill switch: {final_state.get('kill_switch_active')}")
    if final_state.get("report_path"):
        print(f"  Report: {final_state['report_path']}")
    print(f"{'='*60}\n")

    return final_state


def run_simulation(days: int, strategy: str = "threshold"):
    """Fast-forward N days of rebalancing by running one cycle per day."""
    print(f"\nSimulating {days} days of rebalancing ({strategy} strategy)...")
    results = []
    for day in range(days):
        print(f"\n--- Day {day + 1}/{days} ---")
        state = run_agent_cycle(strategy)
        results.append({
            "day": day + 1,
            "trades": len(state.get("trades_executed", [])),
            "kill_switch": state.get("kill_switch_active"),
        })

    print(f"\nSimulation complete: {sum(r['trades'] for r in results)} total trades over {days} days.")
    return results


def init_portfolio():
    """Deploy initial capital across all tickers according to TARGET_ALLOCATION."""
    from market.fetcher import MarketDataService
    from execution.simulator import TradeSimulator

    sim = TradeSimulator()
    fetcher = MarketDataService()

    portfolio = sim.load_portfolio()
    if portfolio.get("positions"):
        print("Portfolio already has positions:")
        for t, q in portfolio["positions"].items():
            print(f"  {t}: {q:.4f}")
        answer = input("\nReset and reinitialise? [y/N] ").strip().lower()
        if answer != "y":
            print("Cancelled.")
            return

    # Reset to clean slate
    import os, json
    from config import INITIAL_CAPITAL, PORTFOLIO_FILE
    clean = {
        "positions": {},
        "cash": INITIAL_CAPITAL,
        "peak_value": INITIAL_CAPITAL,
        "last_rebalanced": None,
        "history": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(clean, f, indent=2)

    print(f"\nFetching live prices for {len(TARGET_ALLOCATION)} tickers...")
    prices = fetcher.get_latest_prices(list(TARGET_ALLOCATION.keys()))

    print(f"\nDeploying ${INITIAL_CAPITAL:,.0f} across target allocation:\n")
    print(f"  {'Ticker':<10} {'Target':>8} {'Price':>10} {'Qty':>10} {'Value':>10}")
    print(f"  {'-'*50}")

    total_deployed = 0.0
    for ticker, weight in TARGET_ALLOCATION.items():
        price = prices.get(ticker, 0)
        if price <= 0:
            print(f"  {ticker:<10}  ⚠ no price available, skipped")
            continue

        dollar_amount = INITIAL_CAPITAL * weight
        qty = dollar_amount / price

        result = sim.execute("buy", ticker, qty, price, reason="Initial portfolio deployment")
        if result.success:
            total_deployed += abs(result.cost)
            print(f"  {ticker:<10} {weight:>7.1%} ${price:>9.2f} {result.quantity:>10.4f} ${abs(result.cost):>9,.0f}")
        else:
            print(f"  {ticker:<10}  ✗ {result.error}")

    portfolio = sim.load_portfolio()
    sim.update_peak(portfolio["cash"] + total_deployed)

    print(f"\n  Cash remaining: ${portfolio['cash']:,.2f}")
    print(f"  Total deployed: ${total_deployed:,.2f}")
    print(f"\nPortfolio initialised. Run 'python main.py' to start the agent.\n")


def generate_report_only():
    """Generate a PDF report from the current portfolio state without running the agent."""
    from agent.tools import generate_report
    cycle_id = str(uuid.uuid4())[:8]
    path = generate_report(cycle_id)
    print(f"Report generated: {path}")
    return path


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Portfolio Rebalancing Agent"
    )
    parser.add_argument(
        "--strategy",
        choices=["threshold", "calendar"],
        default="threshold",
        help="Rebalancing strategy to use (default: threshold)",
    )
    parser.add_argument(
        "--simulate-days",
        type=int,
        default=0,
        metavar="N",
        help="Fast-forward N days of rebalancing cycles",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate PDF report without running the agent",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Deploy initial capital across target allocation and exit",
    )
    args = parser.parse_args()

    if args.init:
        init_portfolio()
        return

    check_api_key()

    if args.report:
        generate_report_only()
    elif args.simulate_days > 0:
        run_simulation(args.simulate_days, args.strategy)
    else:
        run_agent_cycle(args.strategy)


if __name__ == "__main__":
    main()
