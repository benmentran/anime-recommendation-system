#!/bin/bash
docker logs netflix-movie-recommendation-system-recommend_service-1 2>&1 | tail -n 25
