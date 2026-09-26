#!/bin/bash
# Test the live /ask endpoint from inside WSL (no Windows relay needed).
set -u
REPO=/mnt/f/netflix-movie-recommendation-system
cd "$REPO"
export PYTHONPATH="$REPO"
/root/.venv-rag/bin/python -u scripts/wsl_ask_endpoint.py "$@"
