#!/bin/bash
# Run the RAG index job INSIDE WSL: reaches Postgres/Qdrant over the local
# docker bridge even when the WSL2->Windows localhost relay flaps.
# Secrets come from the repo .env at runtime (never stored here).
# Usage: bash /mnt/f/netflix-movie-recommendation-system/scripts/wsl_rag_index.sh [--limit N]
set -u
REPO=/mnt/f/netflix-movie-recommendation-system
cd "$REPO"
echo "STEP1 pwd=$(pwd)"
mkdir -p logs
set -a
eval "$(grep -E '^[A-Z_][A-Z0-9_]*=' .env 2>/dev/null || true)"
set +a
echo "STEP2 key_len=${#OPENAI_API_KEY}"
export PYTHONPATH="$REPO"
echo "STEP3 launching python..."
# Foreground on purpose: WSL sessions kill background jobs on exit.
exec /root/.venv-rag/bin/python pipelines/rag_index.py "$@"
