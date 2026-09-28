#!/bin/bash
# Apply a db/*.sql migration from inside WSL (direct docker-bridge access).
# Usage: bash .../wsl_migrate.sh db/003_multisource.sql
set -u
REPO=/mnt/f/netflix-movie-recommendation-system
cd "$REPO"
set -a
eval "$(grep -E '^[A-Z_][A-Z0-9_]*=' .env 2>/dev/null || true)"
set +a
# Probe localhost first; fall back to container IP when the proxy flaps.
if ! python3 -c "import socket; s=socket.create_connection(('127.0.0.1', 5432), timeout=3); s.close()" 2>/dev/null; then
  eval "$(bash "$REPO/scripts/wsl_pg_url.sh")"
fi
export DATABASE_URL
export PYTHONPATH="$REPO"
/root/.venv-rag/bin/python -u scripts/run_sql_file.py "$1"
