#!/bin/bash
# Install benchmark deps into the WSL RAG venv (pandas + ragas stack).
# langchain-community pinned <0.4 (0.4.x removed chat_models.vertexai ragas needs).
set -u
/root/.venv-rag/bin/pip install -q pandas "langchain-community<0.4" ragas langchain-openai
/root/.venv-rag/bin/python -c "import ragas, pandas; print('BENCH_DEPS_OK', ragas.__version__)"
