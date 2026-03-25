# Lead Report — Prediction Wallet

Reports are append-only. Each session adds a dated section below.

---

## Lead Report: 2026-03-24 14:00
**Last Updated:** 2026-03-24

### Team Status
| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | — | — | No sessions yet |
| ui | — | — | No sessions yet |
| strategy | — | — | No sessions yet |
| usecases | 2026-03-24 — Full Feature Audit | 2026-03-24 | Current |

### Cross-Agent Dependencies

- **usecases → backend**: The `agent/` package and `services/agent_runtime.py` are dead code per usecases. Deletion is a backend task (safe refactor, zero callers confirmed). This is the highest-impact cleanup action and unblocks CLAUDE.md accuracy.
- **usecases → ui**: The Streamlit dashboard (`dashboard/`) is redundant with the HTML/JS UI per usecases. Migration of the Strategy Comparison backtest page to HTML/JS is a UI task that must precede any Streamlit retirement.
- **usecases → backend + ui**: `LocalResearchGateway` feeds the agent a misleading "research_summary" signal. Removing it touches both the service layer (backend) and potentially the MCP wiring (backend/api).
- **No backend/ui/strategy reports yet**: Cannot assess technical quality, implementation risk, or in-progress work for those agents. Priorities below are derived solely from usecases findings.

### Top 3 Priorities

1. **[team-backend]** — Delete `agent/` package and `services/agent_runtime.py` — Zero callers confirmed by usecases grep. These files are silently importable dead code that could mislead contributors. Single cleanup commit. Unblocks CLAUDE.md update.

2. **[team-ui]** — Port Strategy Comparison (backtest) to HTML/JS UI, then retire Streamlit dashboard — The HTML/JS UI is the recommended path (SSE, cleaner design). The only unique Streamlit value is `dashboard/backtest.py`. Migrating it eliminates the dual-UI maintenance burden (every DB schema change currently requires two UI updates).

3. **[team-backend]** — Remove `LocalResearchGateway` and the `local` MCP tools, or replace with a real data source — The `research_summary` injected into agent prompts is trivially derived from data the agent already has. This actively degrades decision quality by presenting reformatted metrics as external research signal. Either cut it entirely or wire to a real API (Finnhub, Alpha Vantage).

### Identified Risks

- **CLAUDE.md drift**: Architecture section still documents `agent/` and `AgentCycleService` as "maintained for compatibility." After the cleanup commit, this must be updated — otherwise onboarding risk persists.
- **Dual-UI schema drift**: Until Streamlit is retired, any `decision_traces` or `agent_runs` schema change will silently break dashboard views that aren't updated.
- **MCP latency with no value**: Running `--use-mcp local` adds subprocess overhead (MCP server spawn + two tool calls) while providing zero incremental data over native tools. Users running the full cycle with `--use-mcp local` incur cost for nothing.
- **Backend/UI/Strategy agents have no reports**: Cannot cross-validate usecases verdicts against implementation complexity. Recommend running `/team-backend`, `/team-ui`, and `/team-strategy` before acting on priorities 1–3 above.

### Recommended Action Plan

**Phase 1 — Cleanup (no feature risk, run next):**
- Run `/team-backend` to get technical assessment of the `agent/` deletion scope and any hidden dependencies before deleting.
- Run `/team-strategy` to confirm no strategy logic accidentally resides in the `agent/` package.
- Delete `agent/` + `services/agent_runtime.py` + update CLAUDE.md in a single commit.
- Remove `LocalResearchGateway` and stop injecting `research_summary` into agent prompts.

**Phase 2 — UI consolidation (medium effort):**
- Run `/team-ui` to get current state of the HTML/JS UI and assess effort to port backtest.
- Port `dashboard/backtest.py` strategy comparison to the HTML/JS UI (new `/backtest` endpoint + UI panel).
- Retire `dashboard/`, `dashboard_main.py`, and Streamlit dependency.

**Phase 3 — MCP (deferred):**
- Keep MCP framework in place as a future extensibility point.
- Remove or disable the `local` profile until `research_summary` is wired to a real data source.

### Stale Reports
- **backend**: No sessions yet — recommend running `/team-backend` before Phase 1 deletions.
- **ui**: No sessions yet — recommend running `/team-ui` before Phase 2 migration.
- **strategy**: No sessions yet — recommend running `/team-strategy` to confirm no strategy logic is entangled with dead `agent/` code.

---

## Lead Report: 2026-03-24 14:30
**Last Updated:** 2026-03-24

### Context

Detailed Phase 1 plan requested. Based on current reports (usecases only).

### Do You Need to Re-run Agents First?

**No — you can proceed directly to Phase 1 without running any agent.**

Rationale:
- **team-usecases already performed grep verification** on every deletion target: zero external callers for `agent/` and `services/agent_runtime.py`, confirmed.
- **CLAUDE.md has already been updated** — references to `agent/` and `AgentCycleService` removed. The "CLAUDE.md drift" risk from the previous report is resolved.
- Phase 1 contains **no logic changes** — only deletions and wiring removals. There is no risk of accidentally altering the critical path (`PortfolioAgentService`).
- The only slightly surgical change (LocalResearchGateway) is handled by grep-before-delete in the plan below.

**When to re-run agents (later, not now):**
- Run `/team-backend` after Phase 1 to get a clean baseline for Phase 2 planning.
- Run `/team-strategy` and `/team-ui` before Phase 2 (backtest migration).

---

### Phase 1 — Complete Step-by-Step Plan

#### Step 1 — Delete the `agent/` package (dead LangGraph code)

Files to delete:
```
agent/__init__.py          (if present)
agent/graph.py
agent/nodes.py
agent/tools.py
agent/state.py
agent/llm.py
agent/prompts.py
agent/__pycache__/         (directory)
```

**Verification before deleting:**
```bash
grep -r "from agent" . --include="*.py" | grep -v "^./agent/"
grep -r "import agent" . --include="*.py" | grep -v "^./agent/"
```
Both should return empty. If not, stop and investigate.

**Risk:** None. usecases confirmed zero external imports.

---

#### Step 2 — Delete `services/agent_runtime.py`

File to delete:
```
services/agent_runtime.py
services/__pycache__/agent_runtime.cpython-*.pyc
```

**Verification before deleting:**
```bash
grep -r "agent_runtime" . --include="*.py"
grep -r "AgentCycleService" . --include="*.py"
```
Both should return empty. If not, stop and investigate.

**Risk:** None. usecases confirmed never imported outside its own file.

---

#### Step 3 — Remove `LocalResearchGateway`

This step requires grepping before acting because the gateway is wired into the agent's dependency injection.

**Grep first:**
```bash
grep -rn "LocalResearchGateway\|research_service\|research_summary" . --include="*.py"
```

Expected wiring points (from usecases):
- `services/research_service.py` — the gateway itself → **delete this file**
- `agents/deps.py` — likely injects `research_summary` into `AgentDependencies` → **remove the field and its construction**
- `agents/models.py` — may have `research_summary: str` in `CycleObservation` → **remove the field**
- `main.py` / `api/runner.py` — may import and pass `LocalResearchGateway` → **remove the import and argument**

**Order of operations:**
1. Delete `services/research_service.py`
2. Edit `agents/deps.py`: remove `research_summary` from `AgentDependencies`
3. Edit `agents/models.py`: remove `research_summary` field from `CycleObservation` (if present)
4. Edit callers (`main.py`, `api/runner.py`): remove construction and passing of `LocalResearchGateway`

**Risk:** Low. The agent will simply stop receiving the misleading `research_summary` field. Existing decision logic is unaffected — this is a context *reduction*, not a change to business logic.

---

#### Step 4 — Disable MCP local tools (`research_summary`)

The MCP *framework* stays intact. Only the two specific tools are addressed.

In `integrations/mcp/server.py`:
- Remove or comment out the `local_research_summary` tool handler
- Optionally remove `local_market_snapshot` (redundant with native `get_market_snapshot`)

In the MCP profile config (likely `profiles/` or `settings.py`):
- Mark the `local` MCP profile as disabled or remove it

**If you prefer a conservative approach:** just remove `local_research_summary` and leave `local_market_snapshot` in place for now. The research gateway is the harmful one; the market snapshot is merely redundant.

**Risk:** Zero. The `local` profile adds latency with no data value. Removing it only improves cycle performance.

---

#### Step 5 — Commit

All four steps above can be committed as a single cleanup commit:
```
chore: remove dead LangGraph agent code and LocalResearchGateway

- Delete agent/ package (graph, nodes, tools, state, llm, prompts)
- Delete services/agent_runtime.py (AgentCycleService)
- Remove LocalResearchGateway and research_summary from agent context
- Disable MCP local research_summary tool

Per usecases audit 2026-03-24: zero external callers confirmed.
PortfolioAgentService critical path unaffected.
```

---

#### Post-Phase-1 Verification

```bash
pytest tests/ -v
python main.py run-cycle --mode simulate
```

Both must pass cleanly before the commit is finalized.

---

### Team Status (updated)
| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | — | — | No sessions yet |
| ui | — | — | No sessions yet |
| strategy | — | — | No sessions yet |
| usecases | 2026-03-24 — Full Feature Audit | 2026-03-24 | Current |

### Notes
- CLAUDE.md already updated (previous session) — no architecture doc work needed in Phase 1.
- Phase 2 (backtest migration + Streamlit retirement) should not start until `/team-ui` has run.
- Phase 3 (MCP upgrade or removal) is deferred indefinitely until a real data source is identified.

---

## Lead Report: 2026-03-24 17:00
**Last Updated:** 2026-03-24

### Context

Phases 1, 2, 3 complètes. Tous les agents ont maintenant des rapports. Premier bilan complet d'équipe.

### Team Status

| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | 2026-03-24 — Dead code cleanup + API hardening | 2026-03-24 16:00 | Current |
| ui | 2026-03-24 — Backtest tab + portfolio improvements | 2026-03-24 16:30 | Current |
| strategy | 2026-03-24 — Engine/strategy analysis (10 priorities) | 2026-03-24 15:00 | Current |
| usecases | 2026-03-24 — Full Feature Audit | 2026-03-24 | Current |

### Ce qui a été accompli (Phases 1–3)

- **Phase 1** : `agent/`, `services/agent_runtime.py`, `services/research_service.py` supprimés. `LocalResearchGateway` retiré du wiring. CLAUDE.md mis à jour. API hardened (`init_db()` + `get_running_loop()`).
- **Phase 2** : `engine/backtest.py` créé, `GET /api/backtest` ajouté, dashboard Streamlit supprimé. L'onglet Backtest HTML/JS est maintenant fonctionnel.
- **Phase 3** : `integrations/mcp/` supprimé. `mcp_profile` retiré de tous les composants (agent, CLI, API, UI). 41/41 tests verts.

### Cross-Agent Dependencies

- **backend → ui** : `MarketSnapshot.research_summary` est toujours présent dans `agents/models.py` avec valeur `""`. Le backend recommande de le supprimer mais demande à team-ui de vérifier si le champ est rendu dans l'UI avant de le retirer. Coordination requise avant suppression.
- **backend → ui** : `pf.pnl_dollars` / `pf.pnl_pct` utilisés dans les stat cards UI — backend doit confirmer que ces champs sont présents dans `portfolio.json` (ou les ajouter à `/api/portfolio`).
- **strategy → backend** : Priority 8 (séparation hard/soft violations dans `agents/policies.py`) est une modification backend pure. Team-strategy l'a identifiée, team-backend confirme que c'est leur scope.
- **Toutes les autres priorités strategy** (1–7, 9–10) sont auto-contenues dans `engine/` et `strategies/` — aucune coordination inter-agents requise.

### Top 3 Priorities

1. **[team-strategy]** — Séparer hard/soft violations dans `agents/policies.py` (Priority 8 strategy) — Un seul ticker bloqué (prix manquant, ETH-USD hors plan) rejette l'intégralité du cycle et annule 8 trades valides. C'est le problème de **correctness** le plus critique : le système peut refuser toutes les exécutions à cause d'un seul edge case. Implémentation auto-contenue.

2. **[team-strategy]** — Tolerance band rebalancing dans `engine/orders.py` (Priority 3 strategy) — Rebalancer vers target ± half-threshold au lieu de target exact. Réduit le turnover de ~30–40%. Implémentation < 1h, aucune coordination requête.

3. **[team-strategy]** — Historical VaR (Priority 1) + Sortino/Calmar (Priority 2) dans `engine/performance.py` — Le `parametric_var` actuel sous-estime systématiquement le risque crypto (fat tails). Historical VaR ne fait aucune hypothèse distributionnelle. Sortino et Calmar sont les métriques standard pour un portefeuille avec kill switch. Ces métriques apparaîtront automatiquement dans le rapport PDF et les traces — aucun changement UI requis.

### Identified Risks

- **Policy engine correctness** (critique) : Un seul trade bloqué annule tout le cycle. En conditions réelles, un ticker sans prix cotée bloquerait toutes les exécutions valides. Voir Priority 8 strategy / open issue #3 backend.
- **`MarketSnapshot.research_summary` champ zombie** : Toujours dans `agents/models.py`, toujours `""`. Risque de confusion pour les futurs développeurs. Coordination backend/ui avant suppression.
- **`CycleAudit.errors` toujours `[]`** : Champ jamais peuplé. Trompe les consommateurs de l'API (dashboard, rapport). Soit peupler, soit supprimer.
- **`api/main.py` raw SQL** : Requêtes SQL dupliquées entre `api/main.py` et `db/repository.py`. Un changement de schéma peut casser l'API silencieusement. Tech debt moyen.
- **Sharpe calculé avec rf=2%** (config hardcodée) : Taux réel 2026 ~4.5%. Le Sharpe rapporté est ~0.25 points trop haut. Affecte la fiabilité des rapports PDF.

### Recommended Action Plan

**Maintenant — aucune coordination requise :**
- Lancer `/team-strategy` pour implémenter les Priorities 1, 2, 3, 4, 5, 7, 8 (engine + strategies + policies).
  - Priority 1 : Historical VaR dans `performance_report`
  - Priority 2 : Sortino + Calmar
  - Priority 3 : Tolerance band rebalancing
  - Priority 4 : Tiered risk levels (OK / WARN / HALT)
  - Priority 5 : rf comme constante config
  - Priority 7 : Calendar drift guard
  - Priority 8 : Hard/soft violation split

**Ensuite — coordination backend/ui :**
- Vérifier si `pf.pnl_dollars`/`pf.pnl_pct` sont dans `portfolio.json` (backend quick check).
- Supprimer `MarketSnapshot.research_summary` de `agents/models.py` après confirmation UI.
- Nettoyer `CycleAudit.errors` (peupler ou supprimer).

**Plus tard — tech debt :**
- Router le SQL de `api/main.py` via `db/repository.py`.
- Init-once flag pour `db/repository._connect()`.

### Stale Reports
(aucun — tous les agents ont des sessions 2026-03-24)

---

## Lead Report: 2026-03-24 18:00
**Last Updated:** 2026-03-24

### Context

L'utilisateur indique avoir terminé de lancer `/team-strategy`. Synthèse post-strategy.

### Team Status

| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | 2026-03-24 16:00 — Dead code cleanup + API hardening | 2026-03-24 16:00 | Current |
| ui | 2026-03-24 16:30 — Backtest tab + portfolio improvements | 2026-03-24 16:30 | Current |
| strategy | 2026-03-24 15:00 — Analysis only (10 priorities identifiées) | 2026-03-24 15:00 | **Stale** ⚠️ |
| usecases | 2026-03-24 — Full Feature Audit | 2026-03-24 | Current |

### ⚠️ Discordance Détectée — Strategy Report

L'utilisateur confirme avoir lancé `/team-strategy`, mais le fichier `docs/team/strategy-report.md` ne contient **qu'une seule session** datée 15:00 (analyse uniquement, pas d'implémentation). Aucune session d'implémentation n'a été appendée.

**Conséquence** : l'état réel du code (engine/, strategies/, policies.py) après le run de team-strategy est **inconnu** depuis les rapports. Le code a peut-être été modifié sans trace dans le rapport d'équipe.

**Action recommandée** : relancer `/team-strategy` pour qu'il appende un rapport d'implémentation, ou inspecter `git log` pour voir ce qui a réellement été commité.

### Cross-Agent Dependencies

Les dépendances en suspens identifiées dans le rapport 17:00 restent ouvertes :

- **backend → ui** : `MarketSnapshot.research_summary` (champ zombie `""`) — coordination requise avant suppression.
- **backend → ui** : `pf.pnl_dollars` / `pf.pnl_pct` — UI affiche `--` si absents. Backend doit confirmer la présence dans `portfolio.json`.
- **strategy → backend/ui** : Si les nouvelles métriques (Sortino, Calmar, VaR historial) ont été ajoutées à `performance_report`, une page Performance dans l'UI serait maintenant justifiée. team-ui l'a mentionné comme amélioration future.

### Top 3 Priorities

1. **[team-strategy]** — Re-run pour confirmer l'état d'implémentation — Le rapport strategy est en phase "analyse seule" et aucune session d'implémentation n'est enregistrée. Sans ce rapport, impossible de savoir si les 10 priorités ont été implémentées ou non. C'est un **blocker pour toute priorisation correcte**.

2. **[team-backend]** — Résoudre les deux items de coordination backend/ui pendants :
   - Vérifier que `portfolio.json` expose `pnl_dollars`/`pnl_pct` (ou les calculer dans `/api/portfolio`)
   - Supprimer `MarketSnapshot.research_summary` de `agents/models.py` après confirmation UI
   Ces deux items sont bloqués depuis le rapport backend 16:00 sans action.

3. **[team-backend]** — Nettoyer `CycleAudit.errors` (toujours `[]`) — Soit peupler le champ depuis les erreurs d'exécution réelles, soit le supprimer du modèle. Champ trompeur pour les consommateurs API et le PDF.

### Identified Risks

- **Implémentation strategy non tracée** : Si team-strategy a modifié `engine/orders.py`, `engine/risk.py`, `agents/policies.py` sans appendre au rapport, les autres agents (backend, ui) n'ont pas de visibilité sur ces changements. Risque de conflits silencieux si backend touche policies.py sans savoir que strategy vient de le modifier.
- **Policy hard/soft split** (Priority 8) : Si non implémentée, reste le problème de correctness le plus critique — un ticker sans prix bloque toutes les exécutions valides.
- **rf hardcodé à 2%** (Priority 5) : Si non corrigé, le Sharpe rapporté reste ~0.25 points trop haut. Tous les rapports PDF générés depuis le début du projet ont un Sharpe biaisé.

### Recommended Action Plan

**Immédiatement :**
1. Relancer `/team-strategy` — obtenir un rapport d'implémentation clair listant ce qui a été fait et ce qui reste.
2. Inspecter `git log --oneline -10` pour voir les commits récents de team-strategy.

**Après confirmation strategy :**
3. Si Priority 8 (policy hard/soft) n'est pas implémentée → la donner à team-backend (scope policies.py).
4. Si nouvelles métriques ajoutées (Sortino, Calmar, VaR) → donner à team-ui la page Performance.
5. Backend quick wins : pnl_dollars/pnl_pct + research_summary cleanup + CycleAudit.errors.

### Stale Reports
- **strategy** : last updated 2026-03-24 15:00 (analyse seule) — **relancer `/team-strategy`** pour obtenir le rapport d'implémentation.

---

## Lead Report: 2026-03-24 18:30
**Last Updated:** 2026-03-24

### Context

Strategy report relu après second run. Diagnostic final sur l'état d'implémentation.

### Team Status

| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | 2026-03-24 16:00 — Dead code cleanup + API hardening | 2026-03-24 16:00 | Current |
| ui | 2026-03-24 16:30 — Backtest tab + portfolio improvements | 2026-03-24 16:30 | Current |
| strategy | 2026-03-24 15:30 — Synthèse priorités (analyse seule, Phase 1) | 2026-03-24 15:30 | Current — **en attente d'implémentation** |
| usecases | 2026-03-24 — Full Feature Audit | 2026-03-24 | Current |

### Diagnostic : Pourquoi team-strategy n'a rien implémenté

Deux sessions d'analyse ont été produites (15:00 + 15:30). Le dernier run a explicitement conclu :

> *"Dire 'proceed with implementation' pour démarrer la Phase 2."*

Team-strategy est un agent **délibératif** : il analyse d'abord, implémente seulement sur confirmation explicite. Rien dans les deux derniers runs ne lui a dit de procéder. Aucun code n'a été modifié.

### Action requise

**Une seule instruction suffit** — relance `/team-strategy` avec un message explicite :

```
/team-strategy proceed with implementation — priorités 1 à 7 du strategy-report
```

Cela couvrira :
- P1 : `historical_var` + VaR 95%/99% + CVaR dans `performance_report`
- P2 : `sortino_ratio` + `calmar_ratio`
- P3 : tolerance band rebalancing dans `engine/orders.py`
- P4 : tiered risk levels (OK/WARN/HALT) dans `engine/risk.py`
- P5 : rf en constante config
- P6 : variable drift bands dans `strategies/threshold.py`
- P7 : calendar drift guard dans `strategies/calendar.py`

Priority 8 (policy hard/soft split) est laissée à team-backend — c'est `agents/policies.py`, hors scope strict de team-strategy.

### Stale Reports
(aucun)

---

## Lead Report: 2026-03-24 19:00
**Last Updated:** 2026-03-24

### Context

Team-strategy a produit une session d'implémentation (Phase 2). Bilan post-implémentation.

### Team Status

| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | 2026-03-24 16:00 — Dead code cleanup + API hardening | 2026-03-24 16:00 | Current |
| ui | 2026-03-24 16:30 — Backtest tab + portfolio improvements | 2026-03-24 16:30 | Current |
| strategy | 2026-03-24 16:00 — Phase 2 implementation (P1–P5) | 2026-03-24 16:00 | Current |
| usecases | 2026-03-24 — Full Feature Audit | 2026-03-24 | Current |

### Ce qui a été implémenté par team-strategy (Priorities 1–5)

| P# | Changement | Fichier |
|----|-----------|---------|
| 1 | `historical_var` + VaR 95/99 + CVaR 95/99 dans `performance_report` | `engine/performance.py` |
| 2 | `sortino_ratio` + `calmar_ratio` dans `performance_report` | `engine/performance.py` |
| 3 | Tolerance band (`min_drift = threshold/2`) dans `generate_rebalance_orders` | `engine/orders.py`, `strategies/` |
| 4 | `RiskLevel` enum (OK/WARN/HALT) + `get_risk_level()` | `engine/risk.py` |
| 5 | `RISK_FREE_RATE = 0.045` en constante config (était 0.02 hardcodé) | `settings.py`, `engine/performance.py` |

30 nouveaux tests dans `tests/test_engine.py` — tous verts.

**Déférés par strategy :** P6 (drift bands variables), P7 (calendar drift guard), P8 (policy hard/soft split).

### ⚠️ Point d'attention : pas de commit git

Le git log ne montre aucun commit de team-strategy. Les changements sont probablement sur disque mais **non commités**. À faire avant de continuer.

### Cross-Agent Dependencies

- **strategy → ui** (débloqué) : `performance_report` expose maintenant 8 nouveaux champs + `RiskLevel`. L'UI peut afficher une page Performance et un indicateur de risque coloré **sans aucun changement backend**. Explicitement validé par strategy.
- **strategy → backend** (P8 non implémenté) : La séparation hard/soft violations dans `agents/policies.py` reste ouverte. Strategy la délègue à team-backend.
- **backend → ui** (toujours ouvert) : `pf.pnl_dollars`/`pf.pnl_pct` non confirmés dans `portfolio.json`. Cards UI affichent `--`.
- **backend → models** (toujours ouvert) : `MarketSnapshot.research_summary` champ zombie (`""`). Coordination backend/ui requise.

### Top 3 Priorities

1. **[team-ui]** — Ajouter une page/section Performance dans l'UI HTML/JS — `performance_report` expose maintenant Sortino, Calmar, VaR 95/99 (param + historique), CVaR 95/99. Aucune modification backend requise. Un indicateur `RiskLevel` coloré (vert/jaune/rouge) via `get_risk_level()` serait directement utilisable via `/api/config` ou un nouvel endpoint. Valeur utilisateur élevée, aucun blocker.

2. **[team-backend]** — Implémenter la séparation hard/soft violations dans `agents/policies.py` (P8 strategy) — Un seul trade bloqué annule tout le cycle. C'est le problème de correctness le plus critique restant. Team-strategy a explicitement délégué ce travail à backend. Scope clair : `agents/policies.py` uniquement.

3. **[team-strategy]** — Implémenter P6 (drift bands variables par actif) + P7 (calendar drift guard) — P6 est la priorité haute restante : BTC/ETH avec 5% de threshold identique à BND génère du sur-trading constant. P7 est trivial (low complexity, skip si drift < 1%). Les deux sont auto-contenus.

### Identified Risks

- **Changements non commités** : team-strategy a modifié `engine/performance.py`, `engine/orders.py`, `engine/risk.py`, `strategies/base.py`, `strategies/threshold.py`, `settings.py`, + 1 nouveau fichier de tests. Aucun commit visible dans `git log`. Risque de perte si la session se ferme.
- **P8 toujours ouvert** (policy correctness) : toujours le risque fonctionnel le plus élevé en conditions réelles.
- **`RISK_FREE_RATE` changé de 2% à 4.5%** : tous les rapports PDF et les métriques précédents avaient un Sharpe biaisé. Rupture de comparabilité historique — à documenter.

### Recommended Action Plan

**Maintenant :**
1. **Commiter** les changements de team-strategy (`git add` + `git commit`).

**Ensuite (ordre recommandé) :**
2. Lancer `/team-ui` — ajouter page Performance + indicateur RiskLevel dans l'UI.
3. Lancer `/team-backend` — implémenter P8 (policy hard/soft split).
4. Lancer `/team-strategy` — implémenter P6 + P7 (drift bands variables + calendar guard).

### Stale Reports
(aucun)

---

## Lead Report: 2026-03-25 10:30
**Last Updated:** 2026-03-25 10:30

### Context

Backend Phase 2 + Strategy Phase 2 complétés. UI Performance tab ajoutée. Bilan complet post-implémentation.

### Team Status

| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | 2026-03-25 10:00 — Policy split + backend hardening (phase 2) | 2026-03-25 10:00 | Current |
| ui | 2026-03-24 17:00 — Performance tab + Portfolio improvements | 2026-03-24 17:00 | Current |
| strategy | 2026-03-25 — Phase 2 implementation (P6+P7+cleanup) | 2026-03-25 | Current |
| usecases | 2026-03-24 — Full Feature Audit | 2026-03-24 | Current |

### Ce qui a été accompli (Backend Phase 2 + Strategy Phase 2)

**Backend Phase 2:**
| Item | Changement | Fichier |
|------|-----------|---------|
| P4 | init-once par chemin DB (`_DB_INITIALIZED: set[str]`) | `db/repository.py` |
| P1 | Policy hard/soft violation split — hard bloque tout, soft bloque seulement le trade | `agents/policies.py` |
| P2 | `CycleAudit.errors` désormais peuplé (violations + exécutions échouées) | `agents/portfolio_agent.py` |
| P5 | SQL déduplication — tous les endpoints API passent par `db/repository.py` | `api/main.py`, `db/repository.py` |
| P3 | SSE subprocess cleanup sur disconnect client (`proc_ref` pattern) | `api/runner.py` |
| Tests | 10 nouveaux tests `tests/test_policies.py` + mise à jour `test_portfolio_agent.py` | 81 tests verts |

**Strategy Phase 2:**
| Item | Changement | Fichier |
|------|-----------|---------|
| P6 | `per_asset_threshold` dans `ThresholdStrategy` (BTC/ETH → 8%, bonds → 3%) | `strategies/threshold.py` |
| P7 | `min_drift` guard dans `CalendarStrategy` (skip si portefeuille déjà équilibré) | `strategies/calendar.py` |
| Boundary | `check_kill_switch`: `< -threshold` → `<= -threshold` | `engine/risk.py` |
| min_notional | Skip trades < $10 dans `generate_rebalance_orders` | `engine/orders.py` |
| Tests | 13 nouveaux tests dans `tests/test_engine.py` (43 total) | |

**UI:**
| Item | Changement | Fichier |
|------|-----------|---------|
| Performance tab | Sharpe, Sortino, Calmar, VaR 95/99, CVaR, Rolling Sharpe chart | `ui/index.html` |

### ⚠️ Point critique : 23 fichiers non commités

`git status` montre 23 fichiers modifiés non commités. Risque de perte si la session se ferme. **Commiter immédiatement avant toute autre action.**

### Cross-Agent Dependencies

- **backend → ui** (toujours ouvert) : `MarketSnapshot.research_summary` champ zombie (`""`) dans `agents/models.py`. Team-ui doit confirmer que le champ n'est pas rendu dans l'UI avant suppression.
- **backend → models** : `run_cycle`/`run_cycle_dict` — vérifier cohérence du threading du paramètre `mcp_profile` (backend open issue #2).
- **strategy → config** : `per_asset_threshold` dans `ThresholdStrategy` devrait être câblé depuis `profiles/*.yaml`. Actuellement hardcodé dans la classe.
- **backend → ui** : `pf.pnl_dollars`/`pf.pnl_pct` — confirmer présence dans `portfolio.json` ou calculer dans `/api/portfolio`.

### Top 3 Priorities

1. **[maintenant]** — Commiter tous les changements non commités — 23 fichiers depuis plusieurs sessions. Backend Phase 2, Strategy Phase 2, UI Performance tab, tests. Risque de perte critique si la session se ferme avant commit.

2. **[team-backend]** — Câbler `per_asset_threshold` depuis `profiles/*.yaml` — Les thresholds par actif (BTC 8%, bonds 3%) sont hardcodés dans `ThresholdStrategy`. Pour qu'ils soient configurables par profil, ils doivent venir de `profiles/*.yaml` via `settings.py`. Changement de config pur, aucun impact logique.

3. **[team-backend ou team-ui]** — Supprimer `MarketSnapshot.research_summary` + confirmer `pnl_dollars`/`pnl_pct` — Deux items de coordination backend/ui ouverts depuis la session 17:00. Le champ `research_summary` toujours `""` trompe les développeurs. Les champs pnl font afficher `--` dans l'UI.

### Identified Risks

- **23 fichiers non commités** : risque immédiat et critique. Toute fermeture de session perd le travail.
- **`per_asset_threshold` hardcodé** : thresholds BTC/ETH/bonds pas configurables par profil. Contourne le système `profiles/*.yaml`.
- **`MarketSnapshot.research_summary` champ zombie** : confusion pour les futurs développeurs, déjà vide depuis Phase 1.
- **`run_cycle` mcp_profile threading** : backend open issue #2 non encore vérifié.

### Recommended Action Plan

**Immédiatement :**
1. `git add` + `git commit` — tous les changements backend Phase 2 + strategy Phase 2 + UI Performance tab.

**Ensuite :**
2. `/team-backend` — câbler `per_asset_threshold` dans `profiles/*.yaml` + vérifier `pnl_dollars`/`pnl_pct` + supprimer `research_summary` après confirmation UI.
3. `/team-ui` — confirmer que `research_summary` n'est pas rendu, puis coordonner la suppression avec backend.

### Stale Reports
(aucun — tous les agents ont des sessions 2026-03-24 ou 2026-03-25)

---

## Lead Report: 2026-03-25 11:30
**Last Updated:** 2026-03-25 11:30

### Context

Bilan après le commit `3968db2` (per_asset_threshold + pnl fix + research_summary cleanup + CLAUDE.md). État de santé général du projet.

### Team Status

| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | 2026-03-25 10:00 — Policy split + backend hardening (phase 2) | 2026-03-25 10:00 | Current |
| ui | 2026-03-24 17:00 — Performance metrics tab | 2026-03-24 17:00 | Current |
| strategy | 2026-03-25 — Phase 2 implementation (P-A à P-E) | 2026-03-25 | Current |
| usecases | 2026-03-24 — Full Feature Audit | 2026-03-24 | **Stale** ⚠️ |

### Résolution des items ouverts depuis le dernier rapport

| Item | Statut |
|------|--------|
| `per_asset_threshold` hardcodé dans `ThresholdStrategy` | ✅ Résolu — câblé depuis `profiles/*.yaml` |
| `pnl_dollars`/`pnl_pct` absents de `/api/portfolio` | ✅ Résolu — calculés depuis `history[-1]` dans l'endpoint |
| `research_summary` dead code dans `ui/index.html` | ✅ Résolu — bloc `researchHtml` supprimé |
| `mcp_profile` threading dans `run_cycle`/`run_cycle_dict` | ✅ Résolu (fausse alarme) — aucune trace de `mcp_profile` dans `portfolio_agent.py` |
| `CLAUDE.md` obsolète (MCP, Streamlit, LangGraph) | ✅ Résolu — sections supprimées, architecture à jour |

### Open Issues restants (cross-agents)

1. **Backend** — Pas de test pour `CycleAudit.errors` — le champ est maintenant peuplé mais aucun test ne couvre ce path. Faible urgence, faible risque.
2. **Backend** — `_DB_INITIALIZED` thread safety : GIL-protégé sous CPython, mais non documenté comme hypothèse. Très faible urgence.
3. **Strategy** — Stress testing / régimes / corrélation : 3 items de complexité moyenne/haute. Aucun n'est un bug — ce sont des améliorations de recherche. Hors scope actuel.
4. **UI** — `hit_ratio` basé sur `success` (simulateur, pas résultat réel) : limitation connue, documentée dans le rapport UI.
5. **README.md** — Toujours obsolète : mentionne MCP, LangGraph, `--use-mcp local`, `dashboard/`, Streamlit. Ne reflète plus l'architecture réelle. Risque onboarding.

### Cross-Agent Dependencies

- (aucune dépendance bloquante) — tous les items ouverts sont auto-contenus.

### Top 3 Priorities

1. **[team-usecases]** — Re-run pour valider les nouvelles fonctionnalités — Depuis le dernier audit (2026-03-24), le projet a reçu : Performance tab, Backtest endpoint fonctionnel, policy hard/soft split, per-asset thresholds, VaR/Sortino/Calmar. Usecases n'a pas évalué ces ajouts. Un audit frais peut identifier des redondances ou des features sans valeur avant qu'elles s'accumulent.

2. **[README.md]** — Mettre à jour le README — Il mentionne encore MCP, LangGraph, `--use-mcp local`, `dashboard/`, Streamlit. Un nouveau développeur lisant le README aurait une image fausse du projet. Correction rapide (< 30 min), aucun risque, impact onboarding direct.

3. **[team-backend]** — Ajouter test pour `CycleAudit.errors` — Le seul item de correctness non couvert par des tests. Un test simple sur le path `audit()` avec une exécution échouée suffit. Complète la couverture de la feature et ferme définitivement l'open issue backend.

### Identified Risks

- **README obsolète** : risque d'onboarding si un nouveau développeur suit les instructions CLI du README (commandes inexistantes, profils MCP supprimés).
- **team-usecases stale** : 3 sessions d'implémentation depuis le dernier audit. Les features ajoutées (Performance tab côté client, Backtest, per-asset thresholds) n'ont pas été évaluées pour leur valeur réelle. Risque de maintenance sur des features peut-être superflues.
- **Stress testing absent** : la stratégie est calibrée sur des conditions normales (yfinance 3mo). En conditions de crise (2020 COVID, 2022 crypto bear), les thresholds et le kill switch à 10% n'ont pas été testés. Risque faible en simulation, critique en paper mode.

### Recommended Action Plan

**État actuel : projet sain, aucun blocker.**

**Court terme (maintenant) :**
1. Mettre à jour `README.md` — suppression références MCP/LangGraph/Streamlit, CLI à jour, architecture réelle.
2. Lancer `/team-usecases` — audit des nouvelles features (Performance tab, Backtest, policy split, per-asset thresholds).

**Moyen terme (après usecases) :**
3. Lancer `/team-backend` — ajouter test `CycleAudit.errors` + documenter hypothèse thread safety.
4. Évaluer les 3 items strategy (stress testing, régimes, corrélation) comme initiative séparée si l'usage paper mode est envisagé.

### Stale Reports
- **usecases** : last updated 2026-03-24 — 3 sessions d'implémentation depuis l'audit. Recommande re-run `/team-usecases`.

---

## Lead Report: 2026-03-25 12:00
**Last Updated:** 2026-03-25 12:00

### Context

Post-usecases re-run (2026-03-25) + backend session 10:30 (CycleAudit.errors tests). README mis à jour. Bilan de clôture du sprint.

### Team Status

| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | 2026-03-25 10:30 — Tests CycleAudit.errors (98 tests) | 2026-03-25 10:30 | Current |
| ui | 2026-03-24 17:00 — Performance metrics tab | 2026-03-24 17:00 | Current |
| strategy | 2026-03-25 — Phase 2 implementation (P-A à P-E) | 2026-03-25 | Current |
| usecases | 2026-03-25 — Post-cleanup audit + dead deps | 2026-03-25 | Current |

### Résolution depuis le dernier rapport (11:30)

| Item | Statut |
|------|--------|
| README obsolète (MCP, LangGraph, Streamlit) | ✅ Résolu — `fec4068` |
| `CycleAudit.errors` non testé | ✅ Résolu — 4 tests ajoutés, 98 tests verts |
| `research_summary` ghost dans backend report | ✅ Fermé — usecases confirme field removed entirely; backend report est stale sur ce point uniquement |
| `/team-usecases` stale | ✅ Résolu — session 2026-03-25 complète |

### Nouveau finding usecases : 8 dépendances mortes

Usecases a identifié 8 packages dans `pyproject.toml` avec **zéro imports** dans le codebase :

| Package | Raison originale | Verdict |
|---------|-----------------|---------|
| `streamlit>=1.40.0` | Dashboard supprimé | **Supprimer** |
| `plotly>=5.18.0` | Charts Streamlit | **Supprimer** |
| `langgraph>=0.2.0` | agent/ supprimé | **Supprimer** |
| `langchain-anthropic>=0.3.0` | agent/ supprimé | **Supprimer** |
| `langchain-core>=0.3.0` | agent/ supprimé | **Supprimer** |
| `mcp[cli]>=1.14.1` | integrations/mcp/ supprimé | **Supprimer** |
| `PyPortfolioOpt>=1.5.5` | Jamais utilisé | **Supprimer** |
| `cvxpy>=1.4.0` | Jamais utilisé | **Supprimer** |

Note : `google-genai` est **à conserver** — utilisé en interne par `pydantic_ai.models.google.GoogleModel`.

### Open Issues restants (cross-agents)

1. **8 dead deps dans `pyproject.toml`** — seul item actionnable immédiatement. Effort : < 5 min. Impact : installation plus rapide, surface de dépendances réduite.
2. **`hit_ratio` basé sur `success` boolean** (strategy P10, deferred) — calcule la proportion d'exécutions réussies, pas le gain réel. Métrique trompeuse dans le rapport PDF. Faible urgence, correctif nécessite du tracking P&L par exécution.
3. **`portfolio_loader.py` absent de CLAUDE.md** — fichier utilisé par `settings.py` et `portfolio_agent.py`, non listé dans la section architecture. Très mineur.
4. **`db/repository._connect()` thread safety** — GIL-protégé, acceptable sous CPython, non documenté. Très faible urgence.
5. **Stress testing absent** — stratégies calibrées sur conditions normales. Critique uniquement si paper mode envisagé.

### Cross-Agent Dependencies

- (aucune) — tous les items restants sont auto-contenus ou de la recherche.

### Top 3 Priorities

1. **[direct, 5 min]** — Supprimer 8 dead deps de `pyproject.toml` + `uv sync` — Usecases l'identifie comme le meilleur rapport valeur/effort actuellement ouvert. 8 lignes supprimées, zéro risque fonctionnel, installation significativement allégée (streamlit + langgraph + plotly + cvxpy sont des packages lourds).

2. **[CLAUDE.md, 2 min]** — Ajouter `portfolio_loader.py` dans la section architecture — Mineur mais le fichier est activement utilisé (`get_active_profile()` appelé par `_get_strategy()`). Complète la documentation d'architecture.

3. **[team-strategy, futur]** — Fixer `hit_ratio` (P10) — Métrique trompeuse dans les rapports PDF : compte les exécutions sans erreur, pas les trades gagnants. Fix nécessite un tracking post-exécution (comparer prix de fill vs prix ultérieur). À planifier si usage paper mode envisagé.

### Identified Risks

- **Dead deps** : `streamlit`, `langgraph`, `cvxpy` sont des packages lourds. Leur présence dans `pyproject.toml` signale à tort qu'ils sont utilisés et allonge le temps d'installation.
- **`hit_ratio` trompeur** : le rapport PDF affiche un "hit ratio" qui mesure les exécutions sans erreur simulateur, pas les trades profitables. Peut induire en erreur si le rapport est partagé.
- **Stress testing** : risque acceptable en simulation. Devient critique avant tout passage en paper mode réel.

### Recommended Action Plan

**État : projet propre. Un seul item à traiter immédiatement.**

1. **Maintenant** : supprimer les 8 dead deps de `pyproject.toml`, lancer `uv sync`, commiter.
2. **Maintenant** : ajouter `portfolio_loader.py` dans CLAUDE.md.
3. **Futur** : `hit_ratio` fix + stress testing comme initiative séparée avant paper mode.

### Stale Reports
(aucun — tous les agents à jour sur 2026-03-25)

---

## Lead Report: 2026-03-25 13:00
**Last Updated:** 2026-03-25 13:00

### Context

Usecases a évalué 15 nouvelles idées de features. 8 acceptées, 7 différées. Une roadmap claire avec un ordre d'implémentation recommandé est désormais disponible.

### Team Status

| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | 2026-03-25 10:30 — Tests CycleAudit.errors (98 tests) | 2026-03-25 10:30 | Current |
| ui | 2026-03-24 17:00 — Performance metrics tab | 2026-03-24 17:00 | Current |
| strategy | 2026-03-25 — Phase 2 implementation (P-A à P-E) | 2026-03-25 | Current |
| usecases | 2026-03-25 — Évaluation 15 nouvelles features | 2026-03-25 | Current |

### Résultats usecases : 8 Accept, 7 Defer, 0 Reject

**Acceptées (à implémenter dans cet ordre) :**

| Étape | Feature | Scope | Raison de l'ordre |
|-------|---------|-------|-------------------|
| 1 | **#15 Explainability** | `ExecutionResult` fields | Fondation : chaque trade aura un audit trail structuré |
| 2 | **#12 Event semantics** | `decision_traces` schema | Migration DB légère, améliore la traçabilité de tout ce qui suit |
| 3 | **#11 Confidence scoring** | `TradeDecision` model | Pydantic seulement, alimente #1 (règles policy sur la confiance) |
| 4 | **#8 Realistic costs** | `engine/orders.py` | Quick win, améliore la précision backtest — #5 en dépend |
| 5 | **#6 Correlation/concentration** | `engine/` + `policies.py` | Résout le risque documenté : 50% concentration tech sans policy check |
| 6 | **#5 Stress testing** | `engine/backtest.py` | Valide le portefeuille sur scénarios de crise (2008, 2020, 2022) |
| 7 | **#1 Policy-as-code** | `agents/policies.py` + YAML | Maintenant outillé : concentration (#6), confiance (#11), coûts (#8) |
| 8 | **#3 Dynamic sizing** | `engine/orders.py` | En dernier — modifie le calcul des quantités cibles |

**Différées (pas maintenant) :** #2 régimes HMM, #4 risk parity, #7 constraint optimization, #9 multi-agent committee, #10 skill registry, #13 adaptive thresholds, #14 walk-forward.

### Cross-Agent Dependencies

- **#1 policy-as-code** dépend de #6 (données corrélation) + #11 (confiance) + #8 (coûts) — ne pas commencer avant les trois.
- **#3 dynamic sizing** est le changement le plus profond (`engine/orders.py`) — en dernier pour ne pas déstabiliser la logique de rebalancement pendant que les autres features se construisent.
- **team-ui** : aucune dépendance bloquante. Les nouvelles features (#15, #12, #11) produiront de nouveaux champs dans les traces — team-ui pourra les afficher une fois stables, sans bloquer l'implémentation.
- **team-strategy** a scope naturel sur #8 (costs), #5 (stress testing), #3 (sizing) — tous dans `engine/`.
- **team-backend** a scope naturel sur #15, #12, #11 (models, persistence), #6 (policy), #1 (policy engine).

### Top 3 Priorities

1. **[team-backend]** — #15 Explainability — Ajouter `policy_checks_passed`, `policy_checks_failed`, `sizing_rationale` dans `ExecutionResult` — C'est la fondation de la roadmap. Chaque trade aura un audit trail structuré dès maintenant. Scope contenu : `agents/models.py` (champs) + `agents/policies.py` (peuplement) + `db/repository.py` (persistance). Usecases le classe comme 1er de la séquence.

2. **[team-strategy]** — #8 Realistic transaction costs — Rendre `apply_slippage()` vol-adjusted et size-adjusted dans `engine/orders.py` — Quick win (< 1h), zéro risque production, améliore immédiatement la précision des backtests. Prérequis pour #5 (stress testing) qui dépend de coûts réalistes.

3. **[team-backend]** — #12 Event semantics — Ajouter `event_type` enum + `tags` JSON dans `decision_traces` (migration schema) — Petite migration DB, améliore la traçabilité analytique. Prépare le terrain pour #11 (confidence) et #1 (policy-as-code).

### Identified Risks

- **Ordre de la roadmap doit être respecté** : commencer #1 policy-as-code avant #6 (corrélation) et #11 (confiance) produira des règles policy sans données réelles pour les alimenter.
- **#3 dynamic sizing en dernier** : modifier les quantités cibles avant que les autres features soient stabilisées risque de rendre les tests des features précédentes invalides.
- **#9 multi-agent trop tôt** : la tentation de sauter à une architecture multi-agent avant que #11 + #15 soient solides est un risque architectural majeur. Usecases est explicite : ne pas commencer #9 avant ces deux prérequis.

### Recommended Action Plan

**Démarrer maintenant (ordre recommandé par usecases) :**
1. `/team-backend` — implémenter #15 (explainability fields in ExecutionResult)
2. `/team-strategy` — implémenter #8 (realistic costs in apply_slippage)
3. `/team-backend` — implémenter #12 (event semantics in decision_traces)

**Ensuite (après 1–3 stables) :**
4. `/team-backend` — #11 confidence scoring (TradeDecision.confidence + data_freshness)
5. `/team-strategy` — #6 correlation/concentration + #5 stress testing
6. `/team-backend` — #1 policy-as-code (hierarchical policy engine)
7. `/team-strategy` — #3 dynamic sizing (inverse-vol weighting)

### Stale Reports
(aucun)

---

## Lead Report: 2026-03-25 14:00
**Last Updated:** 2026-03-25 14:00

### Context

Features #15 (Explainability), #8 (Realistic costs), #12 (Event semantics) implémentées. 124 tests verts. Plan d'action complet pour finir la roadmap usecases.

### Team Status

| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | 2026-03-25 11:00 — #15 + #12 (explainability + event semantics) | 2026-03-25 | Current |
| ui | 2026-03-24 17:00 — Performance metrics tab | 2026-03-24 17:00 | Current |
| strategy | 2026-03-25 — #8 vol-adjusted slippage | 2026-03-25 | Current |
| usecases | 2026-03-25 — Évaluation 15 features | 2026-03-25 | Current |

### Ce qui a été accompli (#15, #8, #12)

| Feature | Ce qui a changé |
|---------|----------------|
| **#15 Explainability** | `ExecutionResult` +5 champs (`weight_before`, `target_weight`, `drift_before`, `slippage_pct`, `notional`). DB migration + `portfolio_agent.execute()` peuple tout. |
| **#12 Event semantics** | `decision_traces` +2 colonnes (`event_type`, `tags`). Tous les 5 call sites peuplés. Taxonomie : `cycle_step`, `kill_switch`, `policy_violation`, `execution_failure`. |
| **#8 Realistic costs** | `apply_slippage()` vol-adjusted et size-adjusted dans `engine/orders.py`. |

**124 tests verts. 12 fichiers non commités.**

### Plan d'action complet — dans l'ordre

**Étape 0 — Commit maintenant** ⚠️
12 fichiers modifiés non commités. Risque de perte si session fermée.

**Étape 1 — `/team-backend` : #11 Confidence scoring**
- `confidence: float` + `data_freshness: str` dans `TradeDecision`
- `data_freshness` calculable depuis `MarketDataStatus.refreshed_at`
- Signal soft uniquement (réduire taille, pas bloquer)
- Prérequis pour #1 policy-as-code

**Étape 2 — `/team-strategy` : #6 Correlation/concentration**
- Rolling correlation matrix (pandas) + score de concentration sectorielle
- Soft block dans `policies.py` si concentration tech > seuil
- Prérequis pour #1 (données corrélation disponibles)

**Étape 3 — `/team-strategy` : #5 Stress testing**
- Scénarios de crise dans `engine/backtest.py` (2008, 2020 COVID, 2022 crypto bear)
- Returns choqués par actif (config dict), zero risque production

**Étape 4 — `/team-backend` : #1 Policy-as-code hiérarchique**
- Ne démarrer qu'après #6 ET #11 — ces deux features alimentent les règles policy
- Hiérarchie global → asset class → ticker → market context
- Config YAML pour les règles

**Étape 5 — `/team-strategy` : #3 Dynamic sizing** (en dernier)
- Inverse-vol weighting dans `engine/orders.py` — opt-in par profil
- ⚠️ Changement le plus profond, stabiliser tout le reste avant

**Étape P1 — `/team-ui` (parallèle, n'importe quand après étape 0)**
- Traces tab : badge `event_type` coloré (kill_switch=rouge, execution_failure=orange)
- Executions tab : colonnes `drift_before`, `slippage_pct`, `notional`

**Étape P2 — Merge feat/agent-team-skills → main**
- Après #11 + #6 + #5 stables, ou dès maintenant si le scope actuel suffit

### Cross-Agent Dependencies

- **#1 policy-as-code** : bloqué par #6 + #11 — ne pas commencer avant les deux
- **#3 dynamic sizing** : en dernier — utilise les mêmes volatilités que #6, évite la duplication
- **#9 multi-agent** (différé) : ne pas commencer avant #11 + #15 stables

### Identified Risks

- **12 fichiers non commités** : risque immédiat — commit étape 0 en priorité absolue
- **`event_type` taxonomy** non documentée dans CLAUDE.md — à ajouter après commit

### Stale Reports
(aucun)

---

## Lead Report: 2026-03-25 16:00
**Last Updated:** 2026-03-25 16:00

### Team Status
| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | 2026-03-25 — #11 confidence scoring + #1 policy-as-code | 2026-03-25 | Current |
| ui | 2026-03-25 — event_type badges + drift_before/slippage_pct columns | 2026-03-25 | Current |
| strategy | 2026-03-25 — #8 vol-adjusted slippage + priorities A–E | 2026-03-25 | Current |
| usecases | 2026-03-25 — 15-feature evaluation (8 Accept, 7 Defer) | 2026-03-25 | Current |

### Roadmap Status — 8 Accepted Features

| # | Feature | Status |
|---|---------|--------|
| #15 | Explainability structurée | ✅ Committed (e384ed0) |
| #12 | Event semantics (event_type + tags) | ✅ Committed (e384ed0) |
| #11 | Confidence scoring + data_freshness | ✅ Committed (cf34f6a) |
| #8  | Vol-adjusted + size-adjusted slippage | ✅ Committed (e384ed0) |
| #6  | Corrélation dynamique + concentration risk | ⚠️ User reports implemented — no source diff found. Likely Phase 1 analysis only. |
| #5  | Stress testing par scénarios | ⚠️ User reports implemented — no source diff found. Likely Phase 1 analysis only. |
| #1  | Policy-as-code hiérarchique | ✅ Committed (cf34f6a) |
| #3  | Dynamic position sizing | ⚠️ User reports implemented — no source diff found. Likely Phase 1 analysis only. |

### Cross-Agent Dependencies
- **#6 (correlation) → #1 (policy)**: PolicyConfig already in place. The sector concentration score (#6) can plug directly into Layer 1 as a soft block. Dependency satisfied.
- **#5 (stress testing) → engine/backtest.py**: Extends the existing backtest infrastructure with scenario definitions. Self-contained.
- **#3 (dynamic sizing) → engine/orders.py**: Inverse-vol weighting mode — deepest change to rebalancing logic. Leave last.

### Top 3 Priorities

1. **[team-strategy]** — Implement #6 correlation/concentration if not yet done — produces `sector_exposure` and `concentration_score` data that feeds into PolicyConfig Layer 1 rules. The strategy report still lists "50% tech concentration unchecked" as an open issue.
2. **[team-strategy]** — Implement #5 stress testing — pure `engine/backtest.py` extension, zero production risk, demonstrates portfolio resilience across 2008/2020/2022 scenarios.
3. **[team-strategy]** — Implement #3 dynamic sizing — inverse-vol weighting in `engine/orders.py`. Now safe: policy engine, confidence scoring, and cost model are all in place to validate the results.

### Identified Risks
- **#6/#5/#3 status unclear**: User reported implementing these but git diff shows no source changes for engine/ or strategies/ beyond what was already committed. Recommend running `/team-strategy` to implement Phase 2 for each of these, or confirming which are actually done.
- **146 tests passing** — baseline is solid. All committed features have test coverage.

### Recommended Action Plan
1. Run `/team-strategy` with prompt "implement #6 correlation/concentration, Phase 2"
2. Run `/team-strategy` with prompt "implement #5 stress testing, Phase 2"
3. Run `/team-strategy` with prompt "implement #3 dynamic sizing, Phase 2"
4. After all 3 done: run `/team-backend` to check if concentration score should be wired into policy Layer 1
5. Once complete: **all 8 Accept features done** → consider opening a PR to merge `feat/agent-team-skills` into `main`

### Stale Reports (if any)
(aucun)

---

## Lead Report: 2026-03-25 17:30
**Last Updated:** 2026-03-25 17:30

### Team Status
| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | 2026-03-25 10:30 — CycleAudit.errors tests | 2026-03-25 | Current |
| ui | 2026-03-25 — event_type badges + drift_before/slippage_pct | 2026-03-25 | Current |
| strategy | 2026-03-25 — #6/#5/#3 all implemented | 2026-03-25 | Current |
| usecases | 2026-03-25 — 15-feature evaluation (8 Accept, 7 Defer) | 2026-03-25 | Current |

### All 8 Accept Features — Final Status

| # | Feature | Implemented | Wired in agent cycle |
|---|---------|-------------|----------------------|
| #15 | Explainability (per-trade audit fields) | ✅ | ✅ `execute()` populates 5 fields |
| #12 | Event semantics (event_type + tags) | ✅ | ✅ all 5 trace call sites |
| #11 | Confidence scoring + data_freshness | ✅ | ✅ `decide()` injects freshness |
| #8  | Vol/size-adjusted slippage | ✅ | ⚠️ optional params — not yet passed from agent |
| #6  | Sector concentration policy check | ✅ | ✅ Layer 2 soft block in PolicyEngine |
| #5  | Stress testing (4 crisis scenarios) | ✅ | ⚠️ standalone — not yet in PDF or API |
| #1  | Policy-as-code (PolicyConfig + 3 layers) | ✅ | ✅ loaded from active profile |
| #3  | Dynamic sizing (inverse-vol weights) | ✅ | ⚠️ optional param — not yet passed from agent |

### Cross-Agent Dependencies

- **#3 → backend**: `volatilities` kwarg ready in strategies but `portfolio_agent.py` doesn't pass vol data yet. `vol_blend` not in profiles/*.yaml. Wire-up is a backend task.
- **#8 → backend**: Same situation — `volatility` param in `apply_slippage` needs per-ticker vol from `MarketService` passed through the agent cycle.
- **#5 → backend/reporting**: `run_stress_test` is ready but not called from `ReportingService`. Wire into PDF as section 7.
- **#6 → config**: `SECTOR_MAP` and `MAX_SECTOR_CONCENTRATION` hardcoded in `config.py`. Future profiles would need their own sector maps — low priority for now.

### Top 3 Priorities

1. **[user + team-backend]** — **Commit & push current changes** — 196 tests passing, all 8 features implemented. Stage: `config.py`, `engine/backtest.py`, `engine/performance.py`, `engine/portfolio.py`, `strategies/base.py`, `strategies/threshold.py`, `strategies/calendar.py`, `agents/policies.py`, `tests/test_engine.py`, `docs/team/`.
2. **[team-backend]** — Wire `volatilities` from MarketService into `portfolio_agent.py → get_trades()` calls and expose `vol_blend` in profiles/*.yaml — this activates dynamic sizing end-to-end. Without this, #3 is implemented but dormant.
3. **[team-backend or team-strategy]** — Wire `run_stress_test` into `ReportingService` PDF (section 7) and expose via `/api/stress` endpoint — stress test results are computed nowhere visible to the user yet.

### Identified Risks

- **Kill switch threshold too conservative**: All 4 stress scenarios (`covid_march_2020`, `gfc_2008`, `rate_shock_2022`, `tech_selloff`) trigger the 10% kill switch. This is accurate modelling — the portfolio WOULD halt — but it also means the kill switch provides zero discrimination between scenarios. The strategy report recommends 15–20%. This is a profile-level config decision (per-profile `kill_switch_drawdown` already supports it).
- **`vol_blend=1.0` cuts crypto target from 20% → ~5%**: With pure inverse-vol weighting, crypto is dramatically underweighted vs profile targets. The strategy report recommends `blend=0.3` as a starting point. Set this when wiring into profiles.
- **`MarketSnapshot.research_summary` still in models.py**: Always `""`. Minor cosmetic noise. Low risk — remove in a cleanup pass.

### Recommended Action Plan

**This session:**
1. Commit + push all changes (196 tests)

**Next sessions (in order):**
2. `/team-backend` — wire `volatilities` into `portfolio_agent.py`, add `vol_blend` to profiles/*.yaml with `default: 0.3`
3. `/team-backend` — wire `run_stress_test` into `ReportingService.generate_pdf()` and add `GET /api/stress` endpoint
4. Optionally: `/team-ui` — add correlation heatmap tab using `rolling_correlation` (data already available in market DB)
5. **Open PR** `feat/agent-team-skills → main` — all 8 features done, 196 tests, no blockers

### Stale Reports (if any)
(aucun)
