#!/bin/bash
# Run PART A cf_matrix INSIDE WSL (uses wsl_pg_url.sh probe for the proxy flap).
# Usage: bash .../wsl_cf_run.sh [--run-name cf_matrix]
set -u
REPO=/mnt/f/netflix-movie-recommendation-system
cd "$REPO"
set -a
eval "$(grep -E '^[A-Z_][A-Z0-9_]*=' .env 2>/dev/null || true)"
set +a
if ! python3 -c "import socket; s=socket.create_connection(('127.0.0.1', 5432), timeout=3); s.close()" 2>/dev/null; then
  eval "$(bash "$REPO/scripts/wsl_pg_url.sh")"
fi
export DATABASE_URL PYTHONPATH="$REPO"
/root/.venv-rag/bin/python -u pipelines/cf_matrix.py "$@"
