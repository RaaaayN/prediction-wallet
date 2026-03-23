# Prediction Wallet

Prediction Wallet est maintenant un **agent financier gouverné** pour portefeuille multi-actifs.  
Son but n’est pas de “trader librement”, mais de:

- observer le portefeuille et le marché,
- produire une décision structurée,
- faire passer cette décision dans une politique déterministe,
- exécuter en simulation ou paper mode,
- auditer chaque étape avec une trace complète.

## Positionnement de l’agent

- **Pydantic AI** est la couche agent principale.
- **MCP** est la frontière standard pour les outils externes sécurisés.
- **LangGraph** n’est plus le chemin critique et reste seulement en compatibilité locale.

## Architecture cible actuellement implémentée

- `agents/`: modèles Pydantic, dépendances, politiques, agent principal
- `integrations/mcp/`: registre de capacités MCP et serveur MCP local
- `services/`: gateways et implémentations locales de marché, exécution, reporting, recherche
- `db/`: snapshots, runs agent, statut marché, decision traces
- `dashboard/`: vue portefeuille, système, et trace de décision

## CLI

```bash
python main.py observe
python main.py decide --mode simulate --use-mcp local
python main.py execute --mode simulate
python main.py audit --mode simulate --use-mcp local
python main.py run-cycle --mode simulate --use-mcp local
python main.py report
python main.py init
```

## Principes de gouvernance

- seule une décision structurée peut être exécutée
- l’agent ne peut approuver que des trades issus du plan déterministe
- le kill switch et les limites de taille restent déterministes
- chaque étape observe / decide / validate / execute / audit est journalisée

## MCP

Le profil MCP `local` expose aujourd’hui:

- `local_market_snapshot`
- `local_research_summary`

Cela sert de base pour brancher plus tard des providers externes marché, news, broker et stockage.
