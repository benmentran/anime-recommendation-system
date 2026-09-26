#!/bin/bash
# Manual RAG ask inside WSL. Usage: bash .../wsl_rag_ask.sh "query" [k]
set -u
REPO=/mnt/f/netflix-movie-recommendation-system
cd "$REPO"
set -a
eval "$(grep -E '^[A-Z_][A-Z0-9_]*=' .env 2>/dev/null || true)"
set +a
export PYTHONPATH="$REPO"
/root/.venv-rag/bin/python -u scripts/wsl_rag_ask.py "$@"
