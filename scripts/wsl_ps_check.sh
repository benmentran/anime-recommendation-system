#!/bin/bash
ps aux | grep -E "rag_index|dockerd" | grep -v grep
echo "PS_DONE"
ls -la /mnt/f/netflix-movie-recommendation-system/data/raw/rag_indexed_ids.txt 2>/dev/null || echo "NO_DONE_FILE"
