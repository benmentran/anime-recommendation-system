#!/bin/bash
# Apply a db/*.sql migration from inside WSL (direct docker-bridge access).
# Usage: bash .../wsl_migrate.sh db/003_multisource.sql
set -u
REPO=/mnt/f/netflix-movie-recommendation-system
cd "$REPO"
set -a
eval "$(grep -E '^[A-Z_][A-Z0-9_]*=' .env 2>/dev/null || true)"
set +a
export DATABASE_URL="${DATABASE_URL:-postgresql://anime:animepass@localhost:5432/anime}"
export PYTHONPATH="$REPO"
/root/.venv-rag/bin/python -u scripts/run_sql_file.py "$1"
