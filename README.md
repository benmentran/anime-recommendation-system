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

## Benchmark (golden set, 30 single-intent + 10 multi-intent rows)

Measured 2026-09-27. Retrieval: Qdrant (`anime`, 5132 points) + `text-embedding-3-small`.
Golden grew 30 → 40 rows: ids 52–61 are multi-intent (`recommend_multi`,
"vừa A vừa B", ent `genre=A;genre=B`). Multi rows stay OUT of P@5/NDCG/MRR
(comparability with the n=30 history) and are scored only by
`intent_recall@5` = fraction of intents with ≥1 slate hit (intent set = ALL
catalog films of that genre, not top-3 — a top-3 set made the metric 0.0
everywhere, a metric artifact, not a retrieval finding).
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
| Metric | Baseline (enriched) | E1 translate (gpt-4o) | E1+H | E3 cross-encoder | BIV bilingual docs | REV reviews (`anime_v3`) |
|---|---|---|---|---|---|---|
| precision@5 | 0.0733 | 0.0667 | 0.0733 | 0.04 | 0.0733 | Pending |
| precision@10 | 0.0367 | 0.0433 | 0.0433 | 0.02 | 0.04 | Pending |
| ndcg@5 | 0.1994 | 0.2634 | 0.2712 | 0.114 | 0.2365 | Pending |
| ndcg@10 | 0.1994 | 0.283 | 0.2858 | 0.114 | 0.2461 | Pending |
| mrr@10 | 0.1856 | 0.2972 | 0.3028 | 0.1111 | 0.2422 | Pending |
| faithfulness (RAGAS) | 0.7671 | — | 0.6791 | — | 0.5857 | — (rescore only if REV wins) |
| answer_relevancy (RAGAS) | 0.2887 | — | 0.2853 | — | 0.2192 | — |
| context_precision (RAGAS) | 0.0956 | — | 0.0956 | — | 0.1417 | — |
| context_recall (RAGAS) | 0.1207 | — | 0.0862 | — | 0.2586 | — |
| answer_correctness (RAGAS) | 0.1139 | — | 0.1215 | — | 0.1035 | — |
| retrieval latency p50 / p95 | 257 / 306 ms | 971 / 1765 ms | 1047 / 1473 ms | 203 / 996 ms | 377 / 949 ms | Pending |
| intent_recall@5 (10 multi rows, retrieval-only) | 0.7 | — | — | — | 0.5 | Pending |
| precision@5 loose, shared-genre (diagnostic only) | 0.80 pure / 0.82 hybrid / 0.8733 E1 | — | — | — | — | Pending |

Verdicts (adopt = P@5 Δ≥+0.05 absolute, MRR not down, p95 < 1.5 s):
E1 translate (gpt-4o) → **REJECT**: ranking lifts (NDCG +0.07, MRR +0.09) but P@5
+0.007 and p95 1.77 s over budget. E1+H → **REJECT**: best ranking (MRR 0.303) yet
faithfulness drops 0.767 → 0.679 and P@5 still +0.013. E3 cross-encoder (ms-marco
MiniLM, local CPU) → **REJECT**: hurts every metric (out-of-domain for VI queries +
anime docs) at +1 GB RAM. BIV bilingual named vectors (`anime_v2`, 5132 pts)
→ **REJECT as default**: best recall story (context_recall 0.121 → 0.259, NDCG
+0.037, MRR +0.057) at zero query-time cost and p95 949 ms in budget — but P@5
flat 0.0733 and faithfulness drops 0.767 → 0.586 (generator cites VI docs
loosely). Multi-intent coverage: baseline 0.7 vs BIV 0.5 (n=10, noisy — no
significant gap either way). Byproduct of the multi rows: they exposed that
`detect_language` routed unaccented Vietnamese ("goi y anime...") to the EN
vector — fixed with unaccented stopwords (minus EN-colliding the/an/hai/...
— locked by tests). Keep collection for recall-side experiments; next is
prompt-side (strict citation + answer in query language), not another
retrieval arm.
Loose scoring ≈ 0.8+ everywhere → diagnostic-only.
Raw per-arm JSONs: `data/golden_dataset/benchmark_<arm>.json`.

Baselines for reference: pure-vector pre-enrichment P@5 0.06, NDCG@5 0.195, MRR 0.2083.
Current docs = enriched (AniList tags+rank/scores/descriptions on all 5132 rows).

Reading guide (honest): translation improves *ranking* but not top-1 precision —
the bottleneck is Vietnamese queries vs English documents compounded by strict
exact-ID relevance. Remaining ideas: bilingual documents, looser relevance as a
first-class metric, in-domain reranker.

## Cold-start simulation (SIMULATED — 1000 virtual users, not real traffic)

Idea borrowed from RecSim (interest-evolution), re-implemented in ~200 lines of
numpy (`scripts/sim_coldstart.py`, no new dependencies). Each virtual user hides
a true taste vector over the 21 real catalog genres (25% single-genre /
55% 2–3-genre mix seeded from real anime combos / 20% eclectic); each round the
arm recommends 5, the user picks via softmax taste-match, taste drifts slightly.
NDCG@5 is scored against the ORIGINAL taste (frozen) so an arm can't inflate its
score by steering the user. Reproduce: `python scripts/sim_coldstart.py`.
Raw JSON: `data/sim/coldstart.json`.

| Strategy | Rounds to NDCG@5 ≥ 0.3 | NDCG@5 after 10 rounds | Intent recall@5 |
|---|---|---|---|
| Popularity-only | never (flat ~0.19) | 0.191 | 0.34 |
| Content-based (2/5 explore slots) | 1 | 0.514 | 0.59 |
| Hybrid (0.7 content + 0.3 popularity) | 1 | 0.452 | 0.61 |

Per-archetype NDCG (content arm): eclectic 0.60 / mix 0.56 / single-genre 0.36 —
niche single-genre tastes stay hardest (few catalog neighbors to learn from).
Engine since 2026-09-28: `pipelines/simulation.py` (unit-norm tastes, L2 items,
fixed-logit no-click option, graded NDCG vs frozen tastes, 4 arms incl. CF-only
and hybrid-switch); `scripts/sim_coldstart.py` is a thin wrapper mapping CLI
flags to it and reshaping the legacy table. Rerun: `python scripts/sim_coldstart.py`.
Two honest findings: (1) with 0 explore slots the content arm locks onto the
wrong genre from round 1 and never recovers (classic exploitation-only trap —
that's why the 2 explore slots exist); (2) binary top-m relevance scored ~0 for
every arm (taste drift moves the slate off the exact top-m ids while staying in
the right neighborhood) — hence graded NDCG, documented in
`graded_ndcg`.
Takeaway for the MVP: hybrid + exploration beats popularity for new users after
~1 interaction; keep popularity as the round-0 fallback.

## Evaluation: real vs simulated

Numbers in this repo come from three different sources — never mix them:

| Source | What | Run tracking |
|---|---|---|
| **Real retrieval** (golden 40 rows) | P@5/NDCG/MRR/RAGAS on Qdrant + OpenAI, measured live | `data/golden_dataset/benchmark_*.json` |
| **Real CF** (PART A) | `user_scores` (Jikan ingestion) → time-split → sparse matrices; stats in run manifest | `artifacts/cf_matrix/<utc>_<sha>/manifest.json` (committed; tables stay local) |
| **Simulated** (PART B) | Cold-start curves with KNOWN ground-truth tastes; no real users involved | `artifacts/simulation/<utc>_<sha>/manifest.json` (`data_source="simulated"`) |

Batch ML code lives in `pipelines/` (plain functions, Airflow-callable, no HTTP):
`run_log.py` (file-based tracking, no server), `metrics.py` (P/R/NDCG/MRR/MAP@k +
`candidate_recall_at_n` = stage-1 Recall@200 ceiling), `cf_matrix.py` (chunked
read → min-count filter → per-user time split → immutable parquet snapshot +
sha256), `simulation.py` (numpy-only user simulator), `candidates.py`
(stage-1 interface; current impl = genre/tag-vector baseline), all config in
`params.yaml` (`pipelines.cf`, `pipelines.simulation`).

Known limitations (honest, not footnotes):
- `user_scores.scored_at` = ingestion time — Jikan animelist entries carry no
  score timestamp. Time-split preserves relative load order only.
- Stage-1 is a genre/tag-vector baseline, not synopsis embeddings. Recall@200
  from this baseline is a floor, not the ceiling of a future embedding stage.
- Sim tastes/temperature/drift are hand-picked (`behavior_track.csv` holds chat
  rubrics, not watch histories — direct calibration is impossible); arm ranking
  is sweep-stable but absolute NDCG values are not transferable to real users.
- No MLflow/DVC in this path by design (`run_log.py` replaces MLflow;
  `dvc.yaml` is legacy MovieLens and unrelated).
Robustness (params are hand-picked — `behavior_track.csv` holds chat rubrics,
not watch histories, so direct calibration is impossible): temperature × drift
sweeps keep the arm ranking everywhere (popularity never reaches NDCG 0.3).
Hybrid weight sweep {0.7, 0.5, 0.3}: more popularity drags hybrid down hard
(0.45 → 0.32 → 0.21 vs content 0.46–0.51) — the popularity term is a round-0
anchor, not a signal source. Keep α=0.7.

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
