#!/bin/bash
docker inspect netflix-movie-recommendation-system-qdrant-1 --format '{{json .State.Health}}' | head -c 2000
echo
docker exec netflix-movie-recommendation-system-qdrant-1 wget -qO- http://localhost:6333/healthz; echo "wget_exit=$?"
docker exec netflix-movie-recommendation-system-qdrant-1 curl -sf http://localhost:6333/healthz; echo "curl_exit=$?"
