"""Golden benchmark: retrieval (P@K/NDCG@K/MRR + latency) + RAGAS 5 metrics + SLO probes.

Reads data/golden_dataset/ragas_track.csv (30 rows). Relevance sets are
re-derived from data/raw/anime_jikan.ndjson with the SAME resolvers used to
build the track (scripts/build_golden_tracks.py), so numbers stay honest.

Needs: Qdrant up (collection `anime`), OPENAI_API_KEY in .env.
Judge model: gpt-4o-mini (cost sanity; generation under test stays gpt-4o).
Writes: data/golden_dataset/benchmark_results.json + prints summary table.
"""
import asyncio
import csv
import json
import math
import os
import sys
import time

REPO = "/mnt/f/netflix-movie-recommendation-system"
sys.path.insert(0, REPO)
os.chdir(REPO)

import httpx  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402

from pipelines.rag_docs import build_document  # noqa: E402
from pipelines.rag_prompt import build_messages  # noqa: E402
from scripts.build_golden_tracks import (  # noqa: E402
    MOOD_GENRES, build_index, genre_rows, load_catalog, parse_titles, resolve,
)

QDRANT = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
COLLECTION = os.getenv("COLLECTION", "anime")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-4o-mini")
K = 10


def relevant_ids(row, exact, contains, rows) -> set[int]:
    """Mirror enrich(): IDs that count as relevant for this question."""
    ent, intent = row["expected_entities"], row["intent"]
    titles = parse_titles(ent)
    resolved = [r for t in titles for r in [resolve(t, exact, contains, rows)] if r]
    if intent == "qa_detail" or "field=" in ent:
        return {resolved[0]["mal_id"]} if resolved else set()
    if intent in ("search", "search_fuzzy") and ("title=" in ent or "title~" in ent):
        return {resolved[0]["mal_id"]} if resolved else set()
    if intent in ("search", "search_fuzzy"):
        pass  # genre/mood query: fall through to genre handling below
    if intent == "compare":
        return {d["mal_id"] for d in resolved[:2]}
    if intent == "recommend" and resolved and any(
            k in ent for k in ("similar_to=", "title=", "title~")):
        base = resolved[0]
        g0 = {str(g.get("name", "")).lower() for g in (base.get("genres") or [])
              if isinstance(g, dict)}
        pool = [d for d in rows if g0 & {
            str(g.get("name", "")).lower() for g in (d.get("genres") or [])
            if isinstance(g, dict)}]
        pool = sorted(pool, key=lambda d: (-(d.get("score") or 0), -(d.get("members") or 0)))
        return {d["mal_id"] for d in
                [x for x in pool if x["mal_id"] != base["mal_id"]][:3]}
    token = ""
    m = __import__("re").search(r"(?:genre|genre/theme)=([^;]+)", ent)
    if m:
        token = m.group(1)
    else:
        low = (ent + " " + row["question"]).lower()
        for mood, gs in MOOD_GENRES.items():
            if mood in low:
                token = gs[0]
                break
        if not token and any(w in low for w in ("hoàn thành", "1 lèo", "cày")):
            done = sorted([d for d in rows if d.get("status") == "Finished Airing"],
                          key=lambda d: -(d.get("score") or 0))[:3]
            return {d["mal_id"] for d in done}
    hits = genre_rows(rows, token) if token else []
    return {d["mal_id"] for d in hits}


def p_at_k(ranked: list[int], rel: set[int], k: int) -> float:
    if not rel:
        return 0.0
    return len([i for i in ranked[:k] if i in rel]) / k


def dcg_at_k(ranked: list[int], rel: set[int], k: int) -> float:
    return sum(1.0 / math.log2(i + 2) for i, mid in enumerate(ranked[:k]) if mid in rel)


def ndcg_at_k(ranked: list[int], rel: set[int], k: int) -> float:
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel), k)))
    return (dcg_at_k(ranked, rel, k) / ideal) if ideal else 0.0


def mrr(ranked: list[int], rel: set[int]) -> float:
    for i, mid in enumerate(ranked):
        if mid in rel:
            return 1.0 / (i + 1)
    return 0.0


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(int(p / 100 * len(xs)), len(xs) - 1)]


async def retrieve(oai, qd, query: str, k: int):
    t0 = time.monotonic()
    emb = await oai.embeddings.create(model=EMBED_MODEL, input=[query])
    r = await qd.post(f"{QDRANT}/collections/{COLLECTION}/points/search",
                      json={"vector": emb.data[0].embedding, "limit": k,
                            "with_payload": True})
    r.raise_for_status()
    dt = (time.monotonic() - t0) * 1000
    return r.json()["result"], dt


REUSE_SAMPLES = "--reuse-samples" in sys.argv


async def main():
    with open("data/golden_dataset/ragas_track.csv", encoding="utf-8") as f:
        gold = list(csv.DictReader(f))
    rows = load_catalog()
    exact, contains, all_rows = build_index(rows)
    oai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    per_row = []
    lat = []
    async with httpx.AsyncClient(timeout=60) as qd:
        for g in gold:
            rel = relevant_ids(g, exact, contains, all_rows)
            hits, ms = await retrieve(oai, qd, g["question"], K)
            lat.append(ms)
            ranked = [h["payload"]["mal_id"] for h in hits]
            ctxs = [h["payload"].get("synopsis") and
                    f"{h['payload'].get('title')} — {h['payload'].get('synopsis')}"
                    for h in hits[:5]]
            per_row.append({"id": g["id"], "group": g["category"], "rel_n": len(rel),
                            "ranked": ranked, "lat_ms": round(ms, 1),
                            "contexts": [c for c in ctxs if c]})
            print(f"row {g['id']}: rel={len(rel)} mrr={mrr(ranked, rel):.2f} "
                  f"p5={p_at_k(ranked, rel, 5):.2f} lat={ms:.0f}ms", flush=True)

    Ps = {k: [] for k in (5, 10)}
    Ns = {k: [] for k in (5, 10)}
    Ms = []
    with open("data/golden_dataset/ragas_track.csv", encoding="utf-8") as f:
        gold2 = {g["id"]: g for g in csv.DictReader(f)}
    for r in per_row:
        rel = relevant_ids(gold2[str(r["id"])], exact, contains, all_rows)
        r["rel_n"] = len(rel)
        for k in (5, 10):
            Ps[k].append(p_at_k(r["ranked"], rel, k))
            Ns[k].append(ndcg_at_k(r["ranked"], rel, k))
        Ms.append(mrr(r["ranked"], rel))
    retr = {"n": len(per_row),
            "precision@5": round(sum(Ps[5]) / len(Ps[5]), 4),
            "precision@10": round(sum(Ps[10]) / len(Ps[10]), 4),
            "ndcg@5": round(sum(Ns[5]) / len(Ns[5]), 4),
            "ndcg@10": round(sum(Ns[10]) / len(Ns[10]), 4),
            "mrr@10": round(sum(Ms) / len(Ms), 4),
            "retrieval_latency_ms_p50": round(pct(lat, 50), 1),
            "retrieval_latency_ms_p95": round(pct(lat, 95), 1)}
    print("RETRIEVAL:", json.dumps(retr, ensure_ascii=False), flush=True)

    # --- generation (gpt-4o) for RAGAS response field ---
    with open("data/golden_dataset/ragas_track.csv", encoding="utf-8") as f:
        gold3 = list(csv.DictReader(f))
    samples = []
    if REUSE_SAMPLES:
        with open("data/golden_dataset/ragas_samples.json", encoding="utf-8") as f:
            samples = json.load(f)
        print(f"REUSED {len(samples)} samples (no regeneration)", flush=True)
    else:
        for g, r in zip(gold3, per_row):
            cands = [{"mal_id": 0, "title": c.split(" — ")[0], "genres": "",
                      "year": None, "score": None,
                      "synopsis": c.split(" — ", 1)[1] if " — " in c else c}
                     for c in r["contexts"]]
            chat = await oai.chat.completions.create(
                model=LLM_MODEL, messages=build_messages(g["question"], cands),
                temperature=0.3, max_tokens=800)
            samples.append({
                "id": g["id"],
                "user_input": g["question"],
                "retrieved_contexts": r["contexts"],
                "response": chat.choices[0].message.content or "",
                "reference": g["reference"],
                "reference_contexts": json.loads(g["reference_contexts"])})
            print(f"generated {g['id']}", flush=True)

    with open("data/golden_dataset/ragas_samples.json", "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False)

    # --- RAGAS scoring (judge: gpt-4o-mini) ---
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    # NOTE: old-style singletons (deprecated in 0.4 but still the only ones
    # accepted by evaluate()); collections.* classes fail its isinstance gate.
    from ragas.metrics import (answer_correctness, answer_relevancy,
                               context_precision, context_recall,
                               faithfulness)
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    ds = EvaluationDataset([SingleTurnSample(**{k: s[k] for k in (
        "user_input", "retrieved_contexts", "response", "reference",
        "reference_contexts")}) for s in samples])
    llm = LangchainLLMWrapper(ChatOpenAI(model=JUDGE_MODEL))
    emb = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(model="text-embedding-3-small"))
    result = evaluate(
        dataset=ds,
        metrics=[faithfulness, answer_relevancy, context_precision,
                 context_recall, answer_correctness],
        llm=llm, embeddings=emb)
    scores = {k: round(float(v), 4) for k, v in result.scores[0].items()
              if k != "id"}
    print("RAGAS:", json.dumps(scores, ensure_ascii=False), flush=True)

    out = {"retrieval": retr, "ragas": scores, "judge_model": JUDGE_MODEL,
           "generator_model": LLM_MODEL, "embed_model": EMBED_MODEL, "rows": per_row}
    with open("data/golden_dataset/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("SAVED data/golden_dataset/benchmark_results.json", flush=True)


asyncio.run(main())
