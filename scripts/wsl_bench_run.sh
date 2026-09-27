#!/bin/bash
# Full golden benchmark inside WSL (retrieval + generation + RAGAS).
set -u
REPO=/mnt/f/netflix-movie-recommendation-system
cd "$REPO"
set -a
eval "$(grep -E '^[A-Z_][A-Z0-9_]*=' .env 2>/dev/null || true)"
set +a
export PYTHONPATH="$REPO"
LOCK="$REPO/logs/bench.lock"
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK")" 2>/dev/null; then
  echo "benchmark already running (pid $(cat "$LOCK")), exiting"
  exit 0
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
/root/.venv-rag/bin/python -u scripts/wsl_benchmark.py "$@"
