#!/bin/bash
# Rebuild RAG venv on python3.11 without ensurepip, then bootstrap pip.
set -u
VENV=/root/.venv-rag
rm -rf "$VENV"
/usr/bin/python3.11 -m venv --without-pip "$VENV"
curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
"$VENV/bin/python" /tmp/get-pip.py
"$VENV/bin/pip" install -q asyncpg openai httpx numpy
"$VENV/bin/python" -c "import asyncpg, openai, httpx, numpy; print('RAG_DEPS_OK')"
"$VENV/bin/python" /mnt/f/netflix-movie-recommendation-system/scripts/wsl_py_loop.py
