#!/bin/bash
# Workstream 8 variant runner (WSL): sources repo .env, runs wsl_benchmark with given flags.
set -u
cd /mnt/f/netflix-movie-recommendation-system
set -a
. /mnt/f/netflix-movie-recommendation-system/.env
set +a
/root/.venv-rag/bin/python scripts/wsl_benchmark.py "$@"
