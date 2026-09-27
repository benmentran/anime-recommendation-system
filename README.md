# Anime Recommendation System

An end-to-end **anime** recommendation system: React frontend, FastAPI BFF,
Postgres persistence, batch `pipelines/` + Airflow, and MLflow-tracked training.

Data sources: **Jikan REST (primary)** + **AniList GraphQL (tag weights, MediaRelation)**.
Images are URL-only (Jikan/AniList CDN) — nothing is downloaded.

## Architecture

```
anime-frontend (React 18 + Vite, Vercel)
        │ 1 origin (VITE_API_URL)
        ▼
web_service (BFF, :8000, JSON /api/v1/*)
   │                │
   │                ├─ Postgres (anime_catalog, user_anime_list, users)
   │                └─ recommend_service (:8001, /api/v1/recommendations/*)
   │                         └─ feature_store_service (:8002, /features/online|historical/*)
   └─ Postgres: anime_raw → anime_catalog (SQL-first transform)

pipelines/ (pure Python, triggered via Airflow UI/CLI — no HTTP):
  ingest → collection (Jikan crawl) → transform → train → simulation
anime_service/ (lib, not a deployment): Jikan/AniList clients + mappers
```

| Component | Runs as | Port |
|---|---|---|
| `web_service` (BFF) | service | 8000 |
| `recommend_service` | service | 8001 |
| `feature_store_service` (merged retrieval) | service | 8002 |
| `postgres:16-alpine` (+ `pgdata` volume) | compose | 5432 |
| `pipelines/*` + Airflow DAGs | batch | — |
| `anime_service` | library | — |
| `anime-frontend` | Vercel | — |

## Target SLOs

Targets, not yet measured. `Measured = Pending` until real runs exist.

| Signal | Target | Measured |
|---|---|---|
| recommend p99 | < 150–200 ms | Pending (`scripts/perf_rag.py` ready; needs live services) |
| BFF p99 | < 300 ms | Pending (same as above) |
| anime browse/detail, DB p95 (graceful degradation on DB miss) | < 500 ms | Pending |
| feature lookup p99 | < 20–30 ms | Pending |
| batch freshness (crawl skip-when-fresh window) | 24 h | **Not met** — last crawl 28 h ago, Airflow not scheduled |

## Benchmark (golden set, 30 RAGAS rows)

Measured 2026-09-27. Retrieval: Qdrant (`anime`, 5132 points) + `text-embedding-3-small`.
Generation: `gpt-4o`. RAGAS judge: `gpt-4o-mini` (cost sanity; generation stays `gpt-4o`).
Reproduce: `bash scripts/wsl_bench_run.sh` (retrieval+generation) then
`python scripts/run_ragas_score.py` (scoring). Raw JSON: `data/golden_dataset/benchmark_results.json`.

| Metric | Measured (Δ vs pure-vector baseline) |
|---|---|
| precision@5 | 0.0733 (+0.013) |
| precision@10 | 0.0367 (±0) |
| ndcg@5 | 0.1994 (+0.004) |
| ndcg@10 | 0.1994 (−0.015) |
| mrr@10 | 0.1856 (−0.023) |
| faithfulness (RAGAS) | 0.7671 (+0.079) |
| answer_relevancy (RAGAS) | 0.2887 (+0.046) |
| context_precision (RAGAS) | 0.0956 (−0.018) |
| context_recall (RAGAS) | 0.1207 (−0.052) |
| answer_correctness (RAGAS) | 0.1139 (−0.034) |
| retrieval latency p50 | ~255 ms |
| retrieval latency p95 | ~320 ms (pure) / 381 ms (hybrid: prefilter narrows search) |
| Metric | Baseline (enriched) | E1 translate (gpt-4o) | E1+H | E3 cross-encoder |
|---|---|---|---|---|
| precision@5 | 0.0733 | 0.0667 | 0.0733 | 0.04 |
| precision@10 | 0.0367 | 0.0433 | 0.0433 | 0.02 |
| ndcg@5 | 0.1994 | 0.2634 | 0.2712 | 0.114 |
| ndcg@10 | 0.1994 | 0.283 | 0.2858 | 0.114 |
| mrr@10 | 0.1856 | 0.2972 | 0.3028 | 0.1111 |
| faithfulness (RAGAS) | 0.7671 | — | 0.6791 | — |
| answer_relevancy (RAGAS) | 0.2887 | — | 0.2853 | — |
| context_precision (RAGAS) | 0.0956 | — | 0.0956 | — |
| context_recall (RAGAS) | 0.1207 | — | 0.0862 | — |
| answer_correctness (RAGAS) | 0.1139 | — | 0.1215 | — |
| retrieval latency p50 / p95 | 257 / 306 ms | 971 / 1765 ms | 1047 / 1473 ms | 203 / 996 ms |
| precision@5 loose, shared-genre (diagnostic only) | 0.80 pure / 0.82 hybrid / 0.8733 E1 | — | — | — |

Verdicts (adopt = P@5 Δ≥+0.05 absolute, MRR not down, p95 < 1.5 s):
E1 translate (gpt-4o) → **REJECT**: ranking lifts (NDCG +0.07, MRR +0.09) but P@5
+0.007 and p95 1.77 s over budget. E1+H → **REJECT**: best ranking (MRR 0.303) yet
faithfulness drops 0.767 → 0.679 and P@5 still +0.013. E3 cross-encoder (ms-marco
MiniLM, local CPU) → **REJECT**: hurts every metric (out-of-domain for VI queries +
anime docs) at +1 GB RAM. Loose scoring ≈ 0.8+ everywhere → diagnostic-only.
Raw per-arm JSONs: `data/golden_dataset/benchmark_<arm>.json`.

Baselines for reference: pure-vector pre-enrichment P@5 0.06, NDCG@5 0.195, MRR 0.2083.
Current docs = enriched (AniList tags+rank/scores/descriptions on all 5132 rows).

Reading guide (honest): translation improves *ranking* but not top-1 precision —
the bottleneck is Vietnamese queries vs English documents compounded by strict
exact-ID relevance. Remaining ideas: bilingual documents, looser relevance as a
first-class metric, in-domain reranker.

## Runbook

```bash
# 1. start Postgres (+ services)
docker compose up --build

# 2. one-time users.json -> Postgres migration (after Postgres is up)
DATABASE_URL=postgresql://anime:animepass@localhost:5432/anime \
  python scripts/migrate_users_json.py

# 3. crawl + transform via Airflow (UI or CLI trigger)
#    DAGs: fetch_extract_features (crawl) -> vectorize_features (transform)
#    or run pipelines directly:
DATABASE_URL=... python -m pipelines.collection 1 5 21
DATABASE_URL=... python -m pipelines.transform
PYTHONPATH=. python pipelines/simulation.py

# 4. tests
python -m pytest tests/ -q
```

Postgres data persists in the `pgdata` named volume. Schema entrypoint: `db/001_init.sql`
(+ `db/002_transform.sql` for the SQL-first transform). Crawl is idempotent:
checkpointed IDs and rows still fresh (`expires_at > NOW()`, 24 h) are skipped.

## Changelog (services removed)

- R1: `tmdb_service` renamed out — anime scope uses `anime_service` (lib);
  `downloader.py` + TMDB pipelines deleted (URL-only images).
- Workstream 2: merged into `pipelines/` and deleted
  `data_ingest_service`, `data_processing_service`, `train_service`,
  `data_collection_service`, `feature_retrieval_service`
  (retrieval merged into `feature_store_service` under `/features`;
  legacy `*_tmdb` routes dropped), `data_simulation_service`
  (rewritten as pure numpy/pandas `pipelines/simulation.py`, RecSim removed).
  History preserved in git.
