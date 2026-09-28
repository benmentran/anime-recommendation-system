#!/bin/bash
# Wait for Postgres, then report interaction + catalog counts.
PG=netflix-movie-recommendation-system-postgres-1
for _ in $(seq 1 24); do
  docker exec "$PG" pg_isready -U anime >/dev/null 2>&1 && break
  sleep 5
done
docker exec "$PG" psql -U anime -d anime -t \
  -c 'SELECT COUNT(*) FROM user_anime_list;' \
  -c 'SELECT COUNT(*) FROM anime_catalog;'
