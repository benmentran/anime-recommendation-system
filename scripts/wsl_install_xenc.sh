#!/bin/bash
set -u
LOG=/tmp/xenc_install.log
nohup /root/.venv-rag/bin/pip install --no-cache-dir sentence-transformers > "$LOG" 2>&1 &
echo "STARTED $!"
