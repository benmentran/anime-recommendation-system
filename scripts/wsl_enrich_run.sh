#!/bin/bash
# AniList enrichment inside WSL. Usage: bash .../wsl_enrich_run.sh [--limit N]
set -u
REPO=/mnt/f/netflix-movie-recommendation-system
cd "$REPO"
set -a
eval "$(grep -E '^[A-Z_][A-Z0-9_]*=' .env 2>/dev/null || true)"
set +a
export PYTHONPATH="$REPO"
/root/.venv-rag/bin/python -u pipelines/anilist_enrich.py "$@"
