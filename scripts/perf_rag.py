"""Measure RAG /ask latency: end-to-end time-to-complete over the BFF.

TTFT does not apply (API returns the full response, no streaming) — so this
script reports time-to-complete per query plus p50/p95/p99. With
`--retrieval-only` it times the retrieval step alone (OpenAI embed + Qdrant
search = closest proxy to time-to-first-candidate).

Run (infra must be live — do NOT reboot the host from here):
    # inside WSL where docker runs:
    docker compose up -d qdrant recommend_service
    OPENAI_API_KEY=... python scripts/perf_rag.py [--base http://localhost:8000] [--n 1]
    OPENAI_API_KEY=... python scripts/perf_rag.py --retrieval-only
Exit 2 with guidance when infra is unreachable (no fake numbers printed).
"""
import json
import os
import statistics
import sys
import time
import urllib.request

BASE = os.getenv("RAG_BASE", "http://localhost:8000")
QDRANT = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
COLLECTION = os.getenv("COLLECTION", "anime")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

QUERIES = [
    "modern political mecha with a villain protagonist",
    "mecha anime about war and politics with child soldiers",
    "romantic comedy anime set in high school",
    "isekai where the main character is overpowered from the start",
    "gợi ý anime tình cảm lãng mạn nhẹ nhàng để xem cuối tuần",
    "anime bóng đá thể thao truyền cảm hứng",
]


def _post(url: str, payload: dict, timeout: int = 120) -> tuple[int, dict, float]:
    data = json.dumps(payload).encode()
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.load(r)
            return r.status, body, time.perf_counter() - t0
    except Exception as e:
        raise RuntimeError(f"POST {url} failed: {e}\n"
                           f"HINT: start infra first (in WSL): "
                           f"docker compose up -d qdrant recommend_service web_service") from e


def _pct(samples: list[float], p: float) -> float:
    if not samples:
        return float("nan")
    s = sorted(samples)
    k = min(int(p / 100 * len(s)), len(s) - 1)
    return s[k]


def end_to_end(base: str, queries: list[str]) -> list[float]:
    lat = []
    for q in queries:
        _st, body, dt = _post(f"{base}/api/v1/rag/ask", {"query": q, "k": 5})
        n = len(body.get("candidates", []))
        print(f"{dt:7.2f}s  n_cands={n}  {q[:70]}", flush=True)
        lat.append(dt)
    return lat


def retrieval_only(queries: list[str]) -> list[float]:
    from openai import AsyncOpenAI  # noqa: runtime import, live-only path
    import asyncio
    import httpx

    async def _one(q: str) -> float:
        oai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        t0 = time.perf_counter()
        emb = await oai.embeddings.create(model=EMBED_MODEL, input=[q])
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{QDRANT}/collections/{COLLECTION}/points/search",
                             json={"vector": emb.data[0].embedding, "limit": 5,
                                   "with_payload": False})
            r.raise_for_status()
        return time.perf_counter() - t0

    lat = []
    for q in queries:
        dt = asyncio.run(_one(q))
        print(f"{dt:7.2f}s  {q[:70]}", flush=True)
        lat.append(dt)
    return lat


def report(lat: list[float]) -> None:
    print(f"n={len(lat)}  p50={_pct(lat, 50):.2f}s  "
          f"p95={_pct(lat, 95):.2f}s  p99={_pct(lat, 99):.2f}s  "
          f"mean={statistics.mean(lat):.2f}s")


if __name__ == "__main__":
    args = sys.argv[1:]
    base = args[args.index("--base") + 1] if "--base" in args else BASE
    try:
        lat = (retrieval_only(QUERIES) if "--retrieval-only" in args
               else end_to_end(base, QUERIES))
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(2)
    report(lat)
