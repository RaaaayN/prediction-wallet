# CLAUDE.md

## Project purpose

Prediction Wallet est un agent financier gouverné:

- il observe un portefeuille multi-actifs,
- produit une décision typée,
- fait valider cette décision par une politique déterministe,
- exécute en simulation/paper mode,
- audite chaque étape.

## Core architecture

- `agents/portfolio_agent.py`: orchestrateur principal Pydantic AI
- `agents/models.py`: schémas Pydantic du cycle agent
- `agents/policies.py`: validation déterministe avant exécution
- `integrations/mcp/`: registre MCP + serveur local
- `db/repository.py`: persistance des runs et des decision traces

## CLI

```bash
python main.py observe
python main.py decide --use-mcp local
python main.py execute
python main.py audit
python main.py run-cycle --mode simulate --use-mcp local
python main.py report
pytest tests/ -v
```

## Important behavior

- l’agent principal est Pydantic AI, pas LangGraph
- MCP est utilisé pour l’outillage externe sécurisé
- le dashboard doit consommer la trace structurée de décision
- les décisions critiques ne doivent jamais dépendre d’un texte libre non validé
