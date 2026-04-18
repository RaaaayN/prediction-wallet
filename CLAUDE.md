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

portfolio_loader.py    — load_profile() / get_active_profile() — charge profiles/*.yaml

runtime_context.py     — build_runtime_context(): chemins portfolio/market.db par profil actif

db/
  schema.py            — DDL: portfolio_snapshots, executions, agent_runs, decision_traces, idea_book…
  repository.py        — persistance SQLite ou PostgreSQL (USE_POSTGRES / DATABASE_URL)

engine/
  portfolio.py         — compute_weights, compute_drift, compute_portfolio_value
  orders.py            — generate_rebalance_orders, apply_slippage, min_drift/min_notional
  risk.py              — compute_drawdown, check_kill_switch, RiskLevel (OK/WARN/HALT)
  performance.py       — performance_report, VaR (parametric + historical), CVaR, Sortino, Calmar
  backtest.py          — run_strategy_comparison (threshold / calendar / buy-and-hold)

frontend/              — UI Vite + React (build → frontend/dist, servi par FastAPI)

ui/
  index.html           — UI monolithique legacy (SSE, tous les onglets)
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

## Roadmap snapshot

- **Fondation**: la gouvernance applicative est déjà en place ou amorcée dans le code (`agents/policies.py`, traces enrichies, init DB durci, repository clarifié), incluant désormais RBAC et contrats API typés.
- **Trading core**: **Phase 1 implémentée** (`trading_core/`). Inclut Security Master, Market Data Handler canonique, OMS v1, Ledger et Simulation Broker Adapter. Intégré de façon opt-in via `TRADING_CORE_ENABLED`.
- **Risk & middle office**: **Phase 1 implémentée** (`services/middle_office_service.py`, `engine/stress_testing.py`). Inclut la réconciliation automatique, le TCA (Transaction Cost Analysis) par cycle, et des stress tests industrialisés par classe d'actifs.

## Architecture Guidelines

### Dynamic Configuration
Le projet utilise un système de configuration dynamique dans `config.py` pour permettre le monkeypatching propre durant les tests (via `sys.modules[__name__].__class__ = ConfigModule`). 
- Toujours importer les constantes depuis `config` (ex: `from config import MARKET_DB`).
- Les composants critiques (`db/connection.py`, `db/repository.py`) résolvent ces valeurs à l'exécution pour honorer les overrides de test.
- Pour isoler un test DB: utiliser `monkeypatch.setattr(config.settings, "market_db", tmp_path / "test.db")` et appeler `db.connection.clear_connection_cache()`.
- Le document de référence pour suivre l'écart entre cible et réel est `deep-research-report (1).md`; les rapports d'équipe dans `docs/team/` donnent le détail d'implémentation courant.
