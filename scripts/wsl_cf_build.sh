#!/bin/bash
# Build real CF matrices from live Postgres, then restart recommend_service.
# Usage: bash scripts/wsl_cf_build.sh
set -e
cd /mnt/f/netflix-movie-recommendation-system
DATABASE_URL=postgresql://anime:animepass@localhost:5432/anime PYTHONPATH=. \
  /root/.venv-rag/bin/python scripts/build_cf_matrices.py
ls -la model/
docker compose -f /mnt/f/netflix-movie-recommendation-system/docker-compose.yml \
  restart recommend_service
sleep 8
docker compose -f /mnt/f/netflix-movie-recommendation-system/docker-compose.yml \
  ps recommend_service
