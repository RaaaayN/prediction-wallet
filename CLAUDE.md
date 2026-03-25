# CLAUDE.md

## Project purpose

Prediction Wallet est un agent financier gouverné:

- il observe un portefeuille multi-actifs,
- produit une décision typée via Pydantic AI,
- fait valider cette décision par une politique déterministe,
- exécute en simulation/paper mode,
- audite chaque étape avec une trace structurée en base.

## Core architecture

```
agents/
  portfolio_agent.py   — orchestrateur Pydantic AI (PortfolioAgentService)
  models.py            — schémas Pydantic: CycleObservation, TradeDecision, CycleAudit...
  policies.py          — ExecutionPolicyEngine (validation déterministe avant exécution)
  deps.py              — AgentDependencies (injection de dépendances)

services/
  execution_service.py — ExecutionService (portefeuille + ordres)
  market_service.py    — MarketService (yfinance → SQLite)
  reporting_service.py — ReportingService (PDF)
  gateways.py          — interfaces communes

db/
  schema.py            — DDL: portfolio_snapshots, executions, agent_runs, decision_traces
  repository.py        — save_snapshot, save_execution, save_agent_run, save_decision_trace

engine/
  portfolio.py         — compute_weights, compute_drift, compute_portfolio_value
  orders.py            — generate_rebalance_orders, apply_slippage, min_drift/min_notional
  risk.py              — compute_drawdown, check_kill_switch, RiskLevel (OK/WARN/HALT)
  performance.py       — performance_report, VaR (parametric + historical), CVaR, Sortino, Calmar
  backtest.py          — run_strategy_comparison (threshold / calendar / buy-and-hold)

ui/
  index.html           — HTML/JS single-page UI (SSE streaming, all tabs)
```

## CLI

```bash
python main.py init
python main.py observe
python main.py decide
python main.py execute
python main.py audit
python main.py run-cycle --mode simulate
python main.py report
pytest tests/ -v
```

## Config & providers

- `AI_PROVIDER=gemini` (défaut) ou `anthropic` — switché via `.env`
- `EXECUTION_MODE=simulate` ou `paper`
- `PORTFOLIO_PROFILE=balanced` (défaut) — switché via `.env` ou `--profile` CLI arg
- `settings.py` + `profiles/*.yaml` sont la source de vérité pour les profils portefeuille
- `profiles/*.yaml` supporte `per_asset_threshold` pour des bandes de drift par actif

## Important behavior

- l'agent principal est **Pydantic AI** (`PortfolioAgentService`) — seul chemin critique
- seule une décision structurée (`TradeDecision`) peut être exécutée
- chaque étape observe/decide/validate/execute/audit est tracée dans `decision_traces`
- le kill switch (drawdown > 10%) est déterministe et bloque toute exécution
- les décisions critiques ne dépendent jamais d'un texte libre non validé
