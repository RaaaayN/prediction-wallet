#!/usr/bin/env bash
# Setup complet : PostgreSQL (Docker), dépendances Python (uv), schéma DB, frontend Vite.
# Usage : ./scripts/setup.sh           # stack complète avec Postgres local
#         ./scripts/setup.sh --sqlite  # sans Docker (SQLite uniquement, chemins data/)

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SQLITE_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --sqlite) SQLITE_ONLY=true ;;
  esac
done

echo "==> Répertoire projet: $ROOT"

if [[ ! -f .env ]]; then
  echo "==> Création .env depuis .env.example"
  cp .env.example .env
  echo "    Édite .env pour GEMINI_API_KEY / ANTHROPIC_API_KEY avant un cycle agent."
else
  echo "==> .env déjà présent (non écrasé)"
fi

if [[ "$SQLITE_ONLY" == true ]]; then
  echo "==> Mode --sqlite : Docker ignoré, pas de DATABASE_URL ajouté."
else
  echo "==> Démarrage PostgreSQL (docker compose)"
  docker compose up -d postgres
  echo "==> Attente pg_isready..."
  for i in $(seq 1 60); do
    if docker compose exec -T postgres pg_isready -U prediction -d prediction_wallet >/dev/null 2>&1; then
      echo "    Postgres prêt."
      break
    fi
    sleep 1
    if [[ "$i" -eq 60 ]]; then
      echo "ERREUR: Postgres n'est pas prêt après 60s." >&2
      exit 1
    fi
  done

  if ! grep -qE '^[[:space:]]*DATABASE_URL=' .env 2>/dev/null; then
    echo "==> Ajout DATABASE_URL dans .env (PostgreSQL local)"
    {
      echo ""
      echo "# PostgreSQL local (docker compose — scripts/setup.sh)"
      echo "DATABASE_URL=postgresql://prediction:prediction@127.0.0.1:5433/prediction_wallet"
    } >> .env
  else
    echo "==> DATABASE_URL déjà défini dans .env"
  fi
fi

echo "==> uv sync (Python 3.13+, groupes dev inclus)"
command -v uv >/dev/null 2>&1 || { echo "Installe uv: https://docs.astral.sh/uv/" >&2; exit 1; }
uv sync --all-groups

echo "==> Initialisation schéma DB (SQLite ou Postgres selon .env)"
uv run python -c "
from db.schema import init_db
from config import MARKET_DB, USE_POSTGRES
init_db(None if USE_POSTGRES else MARKET_DB)
print('Schema OK (USE_POSTGRES=%s)' % USE_POSTGRES)
"

echo "==> Portfolio CLI init (yfinance ; pas besoin des clés LLM)"
set +e
uv run python main.py init
RC=$?
set -e
if [[ "$RC" -ne 0 ]]; then
  echo "    Note: main.py init a échoué (réseau / yfinance). Relance plus tard: uv run python main.py init"
fi

echo "==> Frontend (npm ci + build)"
command -v npm >/dev/null 2>&1 || { echo "Installe Node.js + npm pour le frontend." >&2; exit 1; }
(cd frontend && npm ci && npm run build)

echo ""
echo "=== Setup terminé ==="
echo "  API :  uvicorn api.main:app --reload --host 0.0.0.0 --port 8000"
echo "  UI  :  http://localhost:8000"
if [[ "$SQLITE_ONLY" != true ]]; then
  echo "  DB  :  postgresql://prediction:***@127.0.0.1:5433/prediction_wallet"
fi
