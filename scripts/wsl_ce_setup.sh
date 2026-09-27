#!/bin/bash
# Install cross-encoder stack (CPU) into the WSL RAG venv + pre-download model.
set -u
/root/.venv-rag/bin/pip install -q --force-reinstall --no-cache-dir \
  torch --index-url https://download.pytorch.org/whl/cpu
/root/.venv-rag/bin/pip install -q sentence-transformers
/root/.venv-rag/bin/python -c "
from sentence_transformers import CrossEncoder
m = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('CE_OK', m.predict([('a','b')])[0] > -99)
"
