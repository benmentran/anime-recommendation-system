#!/bin/bash
# Postgres URL that survives the flaky docker-proxy: prefer the container IP
# on the compose bridge, fall back to localhost:5432.
# Usage: eval "$(bash .../wsl_pg_url.sh)"  (sets DATABASE_URL)
IP="$(docker inspect netflix-movie-recommendation-system-postgres-1 \
  --format '{{range $k,$v := .NetworkSettings.Networks}}{{$v.IPAddress}}{{end}}' 2>/dev/null)"
if [ -n "$IP" ] && python3 -c "import socket; s=socket.create_connection(('$IP', 5432), timeout=3); s.close()" 2>/dev/null; then
  echo "export DATABASE_URL=postgresql://anime:animepass@${IP}:5432/anime"
else
  echo "export DATABASE_URL=postgresql://anime:animepass@localhost:5432/anime"
fi
