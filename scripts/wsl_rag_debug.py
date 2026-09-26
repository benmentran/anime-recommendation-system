import sys

print("D1 imports start", flush=True)
sys.path.insert(0, "/mnt/f/netflix-movie-recommendation-system")
import asyncio

print("D2 asyncio ok", flush=True)
import asyncpg

print("D3 asyncpg ok", flush=True)
import httpx

print("D4 httpx ok", flush=True)
from openai import AsyncOpenAI

print("D5 openai ok", flush=True)
from pipelines.rag_docs import build_document

print("D6 rag_docs ok", flush=True)
print("D_ALL_OK", flush=True)
