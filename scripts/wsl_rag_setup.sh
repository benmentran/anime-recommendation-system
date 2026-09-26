#!/bin/bash
# One-time setup: isolated venv inside WSL for RAG jobs.
# Uses python3.11 (system 3.12 has a corrupted asyncio/_ctypes).
# Jobs run here (not Windows) so they reach Postgres/Qdrant over the local
# docker bridge even when the WSL2->Windows localhost relay flaps.
# API key is read from the repo .env at runtime, never stored in this file.
VENV=/root/.venv-rag
rm -rf "$VENV"  # drop the corrupted 3.12 venv, rebuild on 3.11
/usr/bin/python3.11 -m venv "$VENV"
"$VENV/bin/pip" install -q asyncpg openai httpx numpy
"$VENV/bin/python" -c "import asyncpg, openai, httpx, numpy; print('RAG_DEPS_OK')"
"$VENV/bin/python" /mnt/f/netflix-movie-recommendation-system/scripts/wsl_py_loop.py
