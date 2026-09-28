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
if os.path.isdir(REPO):
    sys.path.insert(0, REPO)
    os.chdir(REPO)

import httpx
from openai import AsyncOpenAI

from pipelines.rag_prompt import build_messages
from scripts.build_golden_tracks import (
    MOOD_GENRES,
    build_index,
    genre_rows,
    load_catalog,
    parse_titles,
    resolve,
)

QDRANT = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
COLLECTION = os.getenv("COLLECTION", "anime")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-4o-mini")
K = 10


def relevant_id_sets(row, exact, contains, rows) -> list[set[int]]:
    """Multi-intent rows (intent=recommend_multi, ent genre=A;genre=B):
    one relevant-ID set PER genre. Non-multi rows -> [relevant_ids(...)]."""
    if row.get("intent") == "recommend_multi":
        import re as _re
        tokens = _re.findall(r"(?:genre|genre/theme)=([^;]+)", row.get("expected_entities") or "")
        # Intent = "slate có PHIM THUỘC genre", nên set = TOÀN BỘ phim thuộc genre
        # (không phải top-3 điểm như single-intent).
        sets = [{d["mal_id"] for d in genre_rows(rows, t.strip(), topn=10_000)} for t in tokens]
        return [s for s in sets if s]
    return []


def relevant_ids(row, exact, contains, rows) -> set[int]:
    """Mirror enrich(): IDs that count as relevant for this question."""
    if row.get("intent") == "recommend_multi":
        union: set[int] = set()
        for s in relevant_id_sets(row, exact, contains, rows):
            union |= s
        return union
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
    from pipelines.rag_retrieval import (
        build_qdrant_filter,
        infer_genre_filter,
        rerank_hits,
    )
    global _TRANSLATE_LOGGED
    t0 = time.monotonic()
    orig = query
    if TRANSLATE:
        from pipelines.translate_query import translate_query
        en = await translate_query(query, oai)
        if en != query and _TRANSLATE_LOGGED < 5:
            print(f"TRANSLATED: {query} -> {en}", flush=True)
            _TRANSLATE_LOGGED += 1
        query = en
    _TRANSLATED[orig] = query
    emb = await oai.embeddings.create(model=EMBED_MODEL, input=[query])
    vec = emb.data[0].embedding
    filt = build_qdrant_filter(infer_genre_filter(query)) if HYBRID else None
    limit = CROSS_N if CROSS else (min(k * 2, 10) if filt else k)
    if BIVECTOR:
        from pipelines.rag_retrieval import detect_language
        vecname = "vi" if detect_language(orig) == "vi" else "en"
        body = {"vector": {"name": vecname, "vector": vec},
                "limit": limit, "with_payload": True}
    else:
        body = {"vector": vec, "limit": limit, "with_payload": True}
    if filt:
        body["filter"] = filt
    r = await qd.post(f"{QDRANT}/collections/{COLLECTION}/points/search", json=body)
    if r.status_code == 400 and filt:
        # no full-text index on genres -> fall back to pure vector
        print("prefilter 400, fallback pure-vector", flush=True)
        r = await qd.post(f"{QDRANT}/collections/{COLLECTION}/points/search",
                          json={"vector": vec, "limit": k, "with_payload": True})
    r.raise_for_status()
    dt = (time.monotonic() - t0) * 1000
    hits = r.json()["result"]
    if HYBRID:
        hits = rerank_hits(hits)[:k]
    if CROSS:
        from pipelines.rerank import doc_text, rerank_cross_encoder
        hits = rerank_cross_encoder(query, hits, doc_text, top_k=k)
    elif len(hits) > k:
        hits = hits[:k]
    return hits, dt


REUSE_SAMPLES = "--reuse-samples" in sys.argv
HYBRID = "--hybrid" in sys.argv  # genre prefilter + overfetch + rerank (else pure vector)
BIVECTOR = "--bivector" in sys.argv  # named vectors: vi query -> vi vector, else en
TRANSLATE = "--translate-query" in sys.argv or "--translate" in sys.argv  # VI->EN before embed (V1)
RETRIEVAL_ONLY = "--retrieval-only" in sys.argv  # save retrieval block, skip generation+ragas
SKIP_SCORING = "--skip-scoring" in sys.argv  # save samples, skip ragas scoring
CROSS = "--cross-encoder" in sys.argv  # top-N vector -> cross-encoder rerank -> top-k (V3)
LOOSE = "--loose" in sys.argv  # report loose (shared-genre) metrics alongside strict, no extra retrieval
WITH_GEN = "--with-generation" in sys.argv  # winner arm: bypass retrieval-only early return
REVIEWS = "--reviews" in sys.argv  # reviews arm: expect COLLECTION=anime_v3 (docs + digest)


def _cross_n() -> int:
    for i, a in enumerate(sys.argv):
        if a == "--cross-n" and i + 1 < len(sys.argv):
            try:
                return max(1, int(sys.argv[i + 1]))
            except ValueError:
                pass
    return 20


CROSS_N = _cross_n()
_TRANSLATE_LOGGED = 0
_TRANSLATED: dict[str, str] = {}  # original question -> embedded (possibly translated) query


def _rss_mb() -> float:
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:  # noqa: BLE001 - Windows has no resource module
        return -1.0


def variant_name() -> str:
    parts = []
    if TRANSLATE:
        parts.append("translate")
    if CROSS:
        parts.append("xenc")
    if HYBRID:
        parts.append("hybrid")
    if BIVECTOR:
        parts.append("bivector")
    if REVIEWS:
        parts.append("reviews")
    if parts == ["hybrid"]:
        return "benchmark_hybrid.json"  # legacy name
    if not parts:
        return "benchmark_results.json"  # legacy name
    return f"benchmark_{'_'.join(parts)}.json"


def variant_mode() -> str:
    parts = []
    if TRANSLATE:
        parts.append("translate")
    if CROSS:
        parts.append("xenc")
    if HYBRID:
        parts.append("hybrid")
    if BIVECTOR:
        parts.append("bivector")
    if REVIEWS:
        parts.append("reviews")
    return "+".join(parts) if parts else "pure-vector"


def _max_rows() -> int | None:
    for i, a in enumerate(sys.argv):
        if a == "--max-rows" and i + 1 < len(sys.argv):
            try:
                return max(1, int(sys.argv[i + 1]))
            except ValueError:
                pass
    return None


async def main():
    if REVIEWS and os.getenv("COLLECTION", "anime") == "anime":
        print("WARN: --reviews expects COLLECTION=anime_v3", flush=True)
    with open("data/golden_dataset/ragas_track.csv", encoding="utf-8") as f:
        gold = list(csv.DictReader(f))
    max_rows = _max_rows()
    if max_rows:
        gold = gold[:max_rows]
        print(f"SMOKE: capped to {len(gold)} rows", flush=True)
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
            mem = _rss_mb()
            mem_s = f" rss={mem:.0f}MB" if mem >= 0 else ""
            print(f"row {g['id']}: rel={len(rel)} mrr={mrr(ranked, rel):.2f} "
                  f"p5={p_at_k(ranked, rel, 5):.2f} lat={ms:.0f}ms{mem_s}", flush=True)

    Ps = {k: [] for k in (5, 10)}
    Ns = {k: [] for k in (5, 10)}
    Ms = []
    with open("data/golden_dataset/ragas_track.csv", encoding="utf-8") as f:
        gold2 = {g["id"]: g for g in csv.DictReader(f)}
    IRs = []
    for r in per_row:
        g = gold2[str(r["id"])]
        if g.get("intent") == "recommend_multi":
            # Multi rows KHÔNG vào P@5/NDCG/MRR (giữ comparability với baseline n=30);
            # chúng chỉ đo bằng intent_recall.
            top5 = set(r["ranked"][:5])
            sets = relevant_id_sets(g, exact, contains, all_rows)
            ir = (sum(1 for s in sets if top5 & s) / len(sets)) if sets else 0.0
            r["intent_recall@5"] = round(ir, 4)
            r["rel_n"] = sum(len(s) for s in sets)
            IRs.append(ir)
            continue
        rel = relevant_ids(g, exact, contains, all_rows)
        r["rel_n"] = len(rel)
        for k in (5, 10):
            Ps[k].append(p_at_k(r["ranked"], rel, k))
            Ns[k].append(ndcg_at_k(r["ranked"], rel, k))
        Ms.append(mrr(r["ranked"], rel))
    retr = {"n": len(Ps[5]),  # single-intent rows only; multi rows -> intent_recall@5_multi
            "precision@5": round(sum(Ps[5]) / len(Ps[5]), 4),
            "precision@10": round(sum(Ps[10]) / len(Ps[10]), 4),
            "ndcg@5": round(sum(Ns[5]) / len(Ns[5]), 4),
            "ndcg@10": round(sum(Ns[10]) / len(Ns[10]), 4),
            "mrr@10": round(sum(Ms) / len(Ms), 4),
            "retrieval_latency_ms_p50": round(pct(lat, 50), 1),
            "retrieval_latency_ms_p95": round(pct(lat, 95), 1)}
    if IRs:
        retr["intent_recall@5_multi"] = round(sum(IRs) / len(IRs), 4)
        retr["n_multi"] = len(IRs)
    print("RETRIEVAL:", json.dumps(retr, ensure_ascii=False), flush=True)

    # --- loose rescore (V2): shared-genre relevance, same ranked lists, no extra retrieval ---
    loose = None
    if LOOSE:
        from scripts.score_loose import genre_pool, golden_genres
        from scripts.score_loose import mrr as loose_mrr
        from scripts.score_loose import ndcg_at_k as loose_n
        from scripts.score_loose import p_at_k as loose_p
        by_id = {d["mal_id"]: d for d in rows}
        id_genres = {mid: genre_pool(d) for mid, d in by_id.items()}
        lp, ln, lm = [], [], []
        for r in per_row:
            gg = golden_genres(gold2[str(r["id"])], exact, contains, all_rows)
            rel = {mid for mid in r["ranked"][:10]
                   if gg and (id_genres.get(mid, set()) & gg)}
            lp.append(loose_p(r["ranked"], rel, 5))
            ln.append(loose_n(r["ranked"], rel, 5))
            lm.append(loose_mrr(r["ranked"], rel))
        loose = {"precision@5": round(sum(lp) / len(lp), 4),
                 "ndcg@5": round(sum(ln) / len(ln), 4),
                 "mrr@10": round(sum(lm) / len(lm), 4)}
        print("LOOSE:", json.dumps(loose, ensure_ascii=False), flush=True)

    # --- generation (gpt-4o) for RAGAS response field (skipped in hybrid-only runs) ---
    if max_rows:
        print("SMOKE: skipping save + generation", flush=True)
        if CROSS:
            from pipelines.rerank import release_model

            release_model()
        return
    if (HYBRID or RETRIEVAL_ONLY or TRANSLATE or CROSS or REVIEWS) and not WITH_GEN:
        name = variant_name()
        out = {"retrieval": retr,
               "mode": variant_mode(), "rows": per_row}
        if loose is not None:
            out["loose"] = loose
        if TRANSLATE:
            from pipelines.translate_query import MODEL as TRANSLATE_MODEL

            out["translate_model"] = TRANSLATE_MODEL
        prev = {}
        if os.path.exists(f"data/golden_dataset/{name}"):
            try:
                prev = json.load(open(f"data/golden_dataset/{name}", encoding="utf-8"))
            except (ValueError, OSError):
                prev = {}
        prev.update(out)
        with open(f"data/golden_dataset/{name}", "w", encoding="utf-8") as f:
            json.dump(prev, f, ensure_ascii=False, indent=1)
        print(f"SAVED data/golden_dataset/{name}", flush=True)
        if CROSS:
            from pipelines.rerank import release_model

            release_model()
            print("rerank model released", flush=True)
        return
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
            gen_q = _TRANSLATED.get(g["question"], g["question"])
            chat = await oai.chat.completions.create(
                model=LLM_MODEL, messages=build_messages(gen_q, cands),
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
    # Per-arm copy: ragas_samples.json là slot chung, mỗi arm giữ bản riêng để rescore sau.
    arm = variant_name().removeprefix("benchmark_").removesuffix(".json")
    if arm != "results":
        with open(f"data/golden_dataset/ragas_samples_{arm}.json", "w", encoding="utf-8") as f:
            json.dump(samples, f, ensure_ascii=False)
        print(f"SAVED data/golden_dataset/ragas_samples_{arm}.json", flush=True)
    if SKIP_SCORING:
        print("SKIPPED ragas scoring (--skip-scoring); run "
              "scripts/run_ragas_score.py on Windows", flush=True)
        return

    # --- RAGAS scoring (judge: gpt-4o-mini) ---
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    # NOTE: old-style singletons (deprecated in 0.4 but still the only ones
    # accepted by evaluate()); collections.* classes fail its isinstance gate.
    from ragas.metrics import (
        answer_correctness,
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

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

    out = {"retrieval": retr, "mode": variant_mode(),
           "ragas": scores, "judge_model": JUDGE_MODEL,
           "generator_model": LLM_MODEL, "embed_model": EMBED_MODEL, "rows": per_row}
    if loose is not None:
        out["loose"] = loose
    name = variant_name()
    with open(f"data/golden_dataset/{name}", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"SAVED data/golden_dataset/{name}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
