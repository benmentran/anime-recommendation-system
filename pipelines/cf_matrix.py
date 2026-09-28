"""Real CF matrix from Postgres user_scores (PART A).

Pipeline: chunked read (server cursor, never full table in RAM) -> min-count
filter -> per-user TIME split (last 20% -> test, no leakage) -> immutable
parquet snapshot + sha256 in manifest -> csr matrices (explicit + implicit).

Usage:
    DATABASE_URL=... python pipelines/cf_matrix.py [--run-name cf_matrix]
Airflow-callable: `build_cf_run(run_name)`.
Deps: asyncpg, pandas, pyarrow, scipy. No mlflow/dvc.
"""
import argparse
import os
import sys

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime")


def _cfg():
    try:
        import yaml
        with open("params.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return (cfg.get("pipelines") or {}).get("cf") or {}
    except Exception:  # noqa: BLE001 - optional config, hardcoded defaults apply
        return {}


def filter_min_count(df, min_u: int = 5, min_i: int = 5):
    """Drop users/items with fewer than min interactions (one pass each way)."""

    df = df.copy()
    for _ in range(2):
        cu = df.groupby("user_id")["anime_id"].transform("size")
        df = df[cu >= min_u]
        ci = df.groupby("anime_id")["user_id"].transform("size")
        df = df[ci >= min_i]
    return df.reset_index(drop=True)


def time_split(df, test_frac: float = 0.2):
    """Per-user time split: sort by (scored_at, anime_id), last frac -> test.

    Secondary key anime_id keeps the split deterministic when scored_at ties
    (Jikan ingestion stamps whole users at once) -> digest-stable snapshot.
    Users keep >= 1 train row (k = max(1, round(n*frac)) capped at n-1).
    """

    df = df.sort_values(["user_id", "scored_at", "anime_id"]).reset_index(drop=True)
    test_idx = []
    for _, g in df.groupby("user_id", sort=False):
        n = len(g)
        k = min(max(1, round(n * test_frac)), n - 1)
        test_idx.extend(g.index[-k:].tolist())
    is_test = df.index.isin(test_idx)
    train = df[~is_test].reset_index(drop=True)
    test = df[is_test].reset_index(drop=True)
    train["split"], test["split"] = "train", "test"
    return train, test


def build_id_maps(ids) -> dict:
    """Sorted-id <-> index maps (JSON-serializable, deterministic)."""
    uniq = sorted(set(ids), key=lambda x: (str(type(x)), x))
    return {"id_to_idx": {str(i): n for n, i in enumerate(uniq)},
            "idx_to_id": [i if isinstance(i, (int, float)) else str(i) for i in uniq]}


def to_sparse(df, user_idx: dict, item_idx: dict, implicit: bool = False,
              threshold: int = 7):
    """Ratings frame -> csr_matrix. implicit: score>=threshold -> 1 else 0."""
    from scipy.sparse import csr_matrix

    rows = df["user_id"].map(user_idx).to_numpy()
    cols = df["anime_id"].map(item_idx).to_numpy()
    vals = df["score"].to_numpy(dtype=float)
    if implicit:
        vals = (vals >= threshold).astype(float)
    return csr_matrix((vals, (rows, cols)),
                      shape=(len(user_idx), len(item_idx)))


def matrix_stats(mat) -> dict:
    n, m = mat.shape
    nnz = int(mat.nnz)
    return {"n_users": n, "n_items": m, "nnz": nnz,
            "density": round(nnz / (n * m), 8) if n and m else 0.0}


async def load_interactions_chunked(pool, chunk: int = 10000):
    """Yield DataFrames of user_scores ordered by (user_id, scored_at, anime_id)."""
    import pandas as pd

    async with pool.transaction():
        cur = await pool.cursor(
            "SELECT user_id, anime_id, score, scored_at FROM user_scores "
            "ORDER BY user_id, scored_at, anime_id")
        while True:
            rows = await cur.fetch(chunk)
            if not rows:
                break
            yield pd.DataFrame([dict(r) for r in rows])


async def build_cf_run(run_name: str = "cf_matrix",
                       min_user: "int | None" = None,
                       min_item: "int | None" = None) -> dict:
    """Full pipeline. Returns manifest dict. Raises SystemExit when table empty."""
    import asyncpg
    import pandas as pd

    from pipelines.run_log import start_run

    cfg = _cfg()
    min_u = min_user if min_user is not None else int(cfg.get("min_user_interactions", 5))
    min_i = min_item if min_item is not None else int(cfg.get("min_item_interactions", 5))
    frac = float(cfg.get("test_frac", 0.2))
    thr = int(cfg.get("implicit_threshold", 7))
    chunk = int(cfg.get("chunk_rows", 10000))

    pool = await asyncpg.connect(DATABASE_URL)
    try:
        parts = [df async for df in load_interactions_chunked(pool, chunk)]
    finally:
        await pool.close()
    if not parts:
        raise SystemExit("user_scores is empty; run pipelines/ingest_user_scores.py first")
    df = pd.concat(parts, ignore_index=True)
    df = filter_min_count(df, min_u, min_i)
    if df.empty:
        raise SystemExit("no rows survive min-count filter; lower thresholds in params.yaml")
    train, test = time_split(df, frac)

    uids = sorted(df["user_id"].unique(), key=lambda x: str(x))
    iids = sorted(df["anime_id"].unique())
    user_idx = {u: n for n, u in enumerate(uids)}
    item_idx = {a: n for n, a in enumerate(iids)}

    with start_run(run_name, {"min_user": min_u, "min_item": min_i,
                              "test_frac": frac, "implicit_threshold": thr,
                              "chunk_rows": chunk},
                   data_source="real") as ctx:
        snap = pd.concat([train, test], ignore_index=True)
        snap_path = ctx.dir / "split.parquet"
        snap_sorted = snap.sort_values(by=list(snap.columns)).reset_index(drop=True)
        snap_sorted.to_parquet(snap_path, index=False)
        digest = ctx.set_dataset_file(snap_path)

        train_exp = to_sparse(train, user_idx, item_idx)
        train_imp = to_sparse(train, user_idx, item_idx, implicit=True, threshold=thr)
        stats = {"explicit_train": matrix_stats(train_exp),
                 "implicit_train": matrix_stats(train_imp),
                 "n_train": len(train), "n_test": len(test)}
        ctx.log_metrics(stats)
        ctx.save_json("id_maps_user", build_id_maps(uids))
        ctx.save_json("id_maps_item", build_id_maps(iids))
        import scipy.sparse as _sp

        from pipelines.run_log import sha256_file

        for name, mat in (("train_explicit", train_exp), ("train_implicit", train_imp)):
            p = ctx.dir / f"{name}.npz"
            _sp.save_npz(p, mat)
            ctx.files[p.name] = sha256_file(p)
        print(f"CF_RUN dir={ctx.dir} digest={digest[:12]} stats={stats}", flush=True)
        return ctx.manifest()


def main():
    import asyncio

    ap = argparse.ArgumentParser()
    ap.add_argument("--run-name", default="cf_matrix")
    ap.add_argument("--min-user", type=int, default=None)
    ap.add_argument("--min-item", type=int, default=None)
    args = ap.parse_args()
    asyncio.run(build_cf_run(args.run_name, args.min_user, args.min_item))


if __name__ == "__main__":
    sys.path.insert(0, ".")
    main()
