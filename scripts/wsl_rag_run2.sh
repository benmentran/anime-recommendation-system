#!/bin/bash
set -u
REPO=/mnt/f/netflix-movie-recommendation-system
cd "$REPO"
set -a
eval "$(grep -E '^[A-Z_][A-Z0-9_]*=' .env 2>/dev/null || true)"
set +a
export PYTHONPATH="$REPO"
timeout 120 /root/.venv-rag/bin/python -u scripts/wsl_rag_debug2.py
echo "RUN_EXIT=$?"
