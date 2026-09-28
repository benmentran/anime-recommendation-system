#!/bin/bash
# Print postgres container IP on the compose bridge (bypasses dead port-proxy).
docker inspect netflix-movie-recommendation-system-postgres-1 \
  --format '{{range $k,$v := .NetworkSettings.Networks}}{{$v.IPAddress}}{{end}}'
