# Prediction Wallet

Agent financier gouverné pour portefeuille multi-actifs.
Son but n'est pas de "trader librement", mais de :

- observer le portefeuille et le marché,
- produire une décision structurée via Pydantic AI,
- faire valider cette décision par une politique déterministe,
- exécuter en simulation ou paper mode,
- auditer chaque étape avec une trace complète en base.

## Architecture

```
agents/
  portfolio_agent.py   — orchestrateur Pydantic AI (PortfolioAgentService)
  models.py            — schémas Pydantic : CycleObservation, TradeDecision, CycleAudit...
  policies.py          — ExecutionPolicyEngine (validation déterministe avant exécution)
  deps.py              — AgentDependencies (injection de dépendances)

services/
  execution_service.py — ExecutionService (portefeuille + ordres)
  market_service.py    — MarketService (yfinance → SQLite)
  reporting_service.py — ReportingService (PDF)

engine/
  portfolio.py         — compute_weights, compute_drift, compute_portfolio_value
  orders.py            — generate_rebalance_orders (tolerance bands, min notional)
  risk.py              — compute_drawdown, check_kill_switch, RiskLevel (OK/WARN/HALT)
  performance.py       — VaR (parametric + historical), CVaR, Sortino, Calmar, Sharpe
  backtest.py          — run_strategy_comparison (threshold / calendar / buy-and-hold)

db/
  schema.py            — DDL : portfolio_snapshots, executions, agent_runs, decision_traces
  repository.py        — fonctions de lecture/écriture SQLite

strategies/
  threshold.py         — rebalancement par drift (bandes par actif configurables)
  calendar.py          — rebalancement périodique (weekly / monthly, garde drift min)

ui/
  index.html           — interface HTML/JS (SSE streaming, tous les onglets)

profiles/
  balanced.yaml        — 50% actions, 30% obligations, 20% crypto
  conservative.yaml    — 60% obligations, 40% actions, sans crypto
  growth.yaml          — 70% actions, 20% obligations, 10% crypto
  crypto_heavy.yaml    — 40% actions, 20% obligations, 40% crypto
```

## CLI

```bash
# Initialiser le portefeuille
python main.py init

# Étapes individuelles du cycle
python main.py observe
python main.py decide
python main.py execute
python main.py audit

# Cycle complet
python main.py run-cycle --mode simulate
python main.py run-cycle --mode simulate --strategy calendar

# Rapport PDF
python main.py report

# Tests
pytest tests/ -v
```

## UI web

```bash
uvicorn api.main:app --reload
# Ouvrir http://localhost:8000
```

Onglets disponibles : Portfolio · History · Cycles · Traces · Performance · Backtest · Market Status

## Configuration

Via `.env` ou variables d'environnement :

| Variable | Défaut | Description |
|----------|--------|-------------|
| `AI_PROVIDER` | `gemini` | `gemini` ou `anthropic` |
| `PORTFOLIO_PROFILE` | `balanced` | profil de portefeuille actif |
| `EXECUTION_MODE` | `simulate` | `simulate` ou `paper` |

Les profils (`profiles/*.yaml`) définissent les allocations cibles, les seuils de drift, le kill switch, et les bandes de drift par actif (`per_asset_threshold`).

## Principes de gouvernance

- seule une décision structurée (`TradeDecision`) peut être exécutée
- l'agent ne peut approuver que des trades issus du plan déterministe
- violations **hard** (kill switch, mode live bloqué) : cycle annulé
- violations **soft** (ticker inconnu, prix manquant) : trade bloqué, autres trades poursuivis
- le kill switch (drawdown ≥ 10%) est déterministe et bloque toute exécution
- chaque étape observe / decide / validate / execute / audit est tracée dans `decision_traces`
