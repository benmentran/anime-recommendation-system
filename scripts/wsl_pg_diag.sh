#!/bin/bash
docker ps --format 'TABLE {{.Names}}\t{{.Status}}'
echo "--- pg log tail ---"
docker logs netflix-movie-recommendation-system-postgres-1 2>&1 | tail -n 12
