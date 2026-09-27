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

| Metric | Measured |
|---|---|
| precision@5 | 0.06 |
| precision@10 | 0.0367 |
| ndcg@5 | 0.195 |
| ndcg@10 | 0.2142 |
| mrr@10 | 0.2083 |
| faithfulness (RAGAS) | 0.6883 |
| answer_relevancy (RAGAS) | 0.2425 |
| context_precision (RAGAS) | 0.1133 |
| context_recall (RAGAS) | 0.1724 |
| answer_correctness (RAGAS) | 0.1481 |
| retrieval latency p50 | 264 ms |
| retrieval latency p95 | 998 ms |

Reading guide (honest): faithfulness is decent (answers stay grounded in retrieved
context), but retrieval itself is weak — Vietnamese queries vs English documents plus
strict relevance sets (only top-by-score DB picks count) push P@5 to 0.06, which
cascades into context_precision/recall and answer_correctness. This is exactly why
the hybrid genre-prefilter + rerank workstream exists: re-run this table after it to
prove the lift.

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
