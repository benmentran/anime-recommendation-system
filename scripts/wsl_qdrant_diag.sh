#!/bin/bash
docker ps --format 'TABLE {{.Names}}\t{{.Status}}'
echo "--- qdrant log tail ---"
docker logs netflix-movie-recommendation-system-qdrant-1 2>&1 | tail -n 25
