#!/bin/bash
# Check cross-encoder availability in the WSL RAG venv.
/root/.venv-rag/bin/python -c "
from sentence_transformers import CrossEncoder
m = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('CE_OK')
"
