#!/bin/bash
# Foreground bounded run of the RAG indexer inside WSL.
# Usage: bash .../wsl_rag_run.sh [--limit N]
set -u
REPO=/mnt/f/netflix-movie-recommendation-system
cd "$REPO"
echo "RUN_START"
set -a
eval "$(grep -E '^[A-Z_][A-Z0-9_]*=' .env 2>/dev/null || true)"
set +a
export PYTHONPATH="$REPO"
timeout 280 /root/.venv-rag/bin/python -u pipelines/rag_index.py "$@"
echo "RUN_EXIT=$?"
