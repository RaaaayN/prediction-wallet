"""CLI entry point for the governed portfolio agent."""

from __future__ import annotations

import argparse
import json
import os
import sys

from agents.portfolio_agent import PortfolioAgentService
from config import AGENT_BACKEND, AI_PROVIDER, EXECUTION_MODE


def check_api_key():
    from config import ANTHROPIC_API_KEY, GEMINI_API_KEY

    if AI_PROVIDER == "gemini" and not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set.")
        sys.exit(1)
    if AI_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)


def print_json(payload) -> None:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    print(json.dumps(payload, indent=2, default=str))


def init_portfolio(force: bool = False, initial_capital: float | None = None):
    from config import INITIAL_CAPITAL, TARGET_ALLOCATION
    from execution.simulator import TradeSimulator
    from market.fetcher import MarketDataService
    from utils.time import utc_now_iso

    sim = TradeSimulator()
    fetcher = MarketDataService()
    portfolio = sim.load_portfolio()

    if portfolio.get("positions") and not force:
        answer = input("Portfolio already has positions. Reset and reinitialize? [y/N] ").strip().lower()
        if answer != "y":
            print("Cancelled.")
            return

    capital = initial_capital if initial_capital is not None else INITIAL_CAPITAL

    clean = {
        "positions": {},
        "position_sides": {},
        "average_costs": {},
        "cash": capital,
        "peak_value": capital,
        "last_rebalanced": None,
        "history": [],
        "created_at": utc_now_iso(),
    }
    sim.save_portfolio(clean)

    prices = fetcher.get_latest_prices(list(TARGET_ALLOCATION.keys()))
    if sum(TARGET_ALLOCATION.values()) > 0:
        for ticker, weight in TARGET_ALLOCATION.items():
            price = prices.get(ticker, 0)
            if price <= 0:
                print(f"Skipping {ticker}: No valid price found.")
                continue
            quantity = (capital * weight) / price
            res = sim.execute("buy", ticker, quantity, price, reason="Initial portfolio deployment", prices=prices)
            if res.success:
                print(f"Allocated {quantity:.4f} {ticker} @ {price:.2f}")
            else:
                print(f"Failed to allocate {ticker}: {res.error}")
    print("Portfolio initialized.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Governed multi-asset portfolio agent")
    parser.add_argument("--profile", choices=["balanced", "conservative", "growth", "crypto_heavy", "long_short_equity"], default=None)
    parser.add_argument("--strategy", choices=["threshold", "calendar"], default="threshold")
    parser.add_argument("--mode", choices=["simulate", "paper", "live"], default=EXECUTION_MODE)
    parser.add_argument("--agent-backend", choices=["pydantic-ai"], default=AGENT_BACKEND)
    parser.add_argument("--simulate-days", type=int, default=0, metavar="N")

    subparsers = parser.add_subparsers(dest="command")
    for name in ["observe", "decide", "execute", "audit", "run-cycle"]:
        sub = subparsers.add_parser(name)
        sub.add_argument("--strategy", choices=["threshold", "calendar"], default="threshold")
        sub.add_argument("--mode", choices=["simulate", "paper", "live"], default=EXECUTION_MODE)
        sub.add_argument("--agent-backend", choices=["pydantic-ai"], default=AGENT_BACKEND)
        sub.add_argument("--profile", choices=["balanced", "conservative", "growth", "crypto_heavy", "long_short_equity"], default=None)
    subparsers.add_parser("report")
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing portfolio without prompt")
    init_parser.add_argument("--initial-capital", type=float, help="Override initial capital from profile")
    return parser


def generate_report_only():
    from services.execution_service import ExecutionService
    from services.market_service import MarketService
    from services.reporting_service import ReportingService
    import uuid

    cycle_id = str(uuid.uuid4())[:8]
    path = ReportingService(
        market_service=MarketService(),
        execution_service=ExecutionService(),
    ).generate_cycle_report(cycle_id)
    print(path)


def run_days(service: PortfolioAgentService, days: int, strategy: str, mode: str):
    audits = []
    for _ in range(days):
        audits.append(service.run_cycle(strategy_name=strategy, execution_mode=mode))
    print_json([audit.model_dump() for audit in audits])


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.profile:
        os.environ["PORTFOLIO_PROFILE"] = args.profile

    command = args.command or "run-cycle"

    if command == "init":
        init_portfolio(
            force=getattr(args, "force", False),
            initial_capital=getattr(args, "initial_capital", None)
        )
        return
    if command == "report":
        generate_report_only()
        return

    service = PortfolioAgentService()

    if args.simulate_days > 0:
        check_api_key()
        run_days(service, args.simulate_days, args.strategy, args.mode)
        return

    observation = service.observe(strategy_name=args.strategy, execution_mode=args.mode)
    if command == "observe":
        print_json(observation)
        return

    check_api_key()
    decision, stats = service.decide(observation, execution_mode=args.mode)
    if command == "decide":
        print_json({"observation": observation.model_dump(), "decision": decision.model_dump(), "observability": stats})
        return

    policy, executions = service.execute(observation, decision, execution_mode=args.mode)
    if command == "execute":
        print_json(
            {
                "observation": observation.model_dump(),
                "decision": decision.model_dump(),
                "policy": policy.model_dump(),
                "executions": [e.model_dump() for e in executions],
            }
        )
        return

    audit = service.audit(observation, decision, policy, executions, execution_mode=args.mode)
    print_json(audit)


if __name__ == "__main__":
    main()
