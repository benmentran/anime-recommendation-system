"""Build CF matrices once, save to model/*.pkl (DVC-tracked). APIs only load.

Reads implicit feedback from user_anime_list + item features from
anime_catalog, trains UserBasedCF / ItemBasedCF / ContentBasedFiltering
(pure numpy/pandas, no mlflow), pickles fitted objects + popularity list.
App restart picks up new matrices (no retrain per request).

Status -> rating weight: completed 1.0, watching 0.7, plan_to_watch 0.2,
on_hold 0.3, dropped 0.0. Explicit user score (1-10) wins when present.

Usage: DATABASE_URL=... python scripts/build_cf_matrices.py [--out model]
"""
import asyncio
import json
import os
import pickle
import sys
from pathlib import Path

import asyncpg
import numpy as np
import pandas as pd

STATUS_WEIGHT = {"completed": 1.0, "watching": 0.7, "plan_to_watch": 0.2,
                 "on_hold": 0.3, "dropped": 0.0}

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime")


def status_frame(rows: list[dict]) -> pd.DataFrame:
    """user_anime_list rows -> ratings(user_id, item_id, rating). Pure, tested."""
    out = []
    for r in rows:
        if r.get("score"):
            rating = float(r["score"]) / 10.0
        else:
            rating = STATUS_WEIGHT.get(r.get("status"), 0.0)
        if rating > 0:
            out.append({"user_id": r["user_id"], "item_id": r["anime_id"],
                        "rating": rating})
    return pd.DataFrame(out, columns=["user_id", "item_id", "rating"])


def item_feature_frame(catalog: list[dict]):
    """Catalog rows -> (features df, vocab). Binary genres + tag weights/100."""
    vocab = set()
    parsed = []
    for r in catalog:
        genres = r["genres"]
        genres = json.loads(genres) if isinstance(genres, str) else (genres or [])
        tags = r.get("tags_anilist")
        tags = json.loads(tags) if isinstance(tags, str) else (tags or [])
        tagmap = {t["name"]: (t.get("weight") or 0) / 100.0
                  for t in tags if isinstance(t, dict) and t.get("name")}
        parsed.append((r["mal_id"], set(genres), tagmap))
        vocab.update(genres)
        vocab.update(tagmap)
    vocab = sorted(vocab)
    idx = {v: i for i, v in enumerate(vocab)}
    mat, ids = [], []
    for mal_id, genres, tagmap in parsed:
        vec = np.zeros(len(vocab))
        for g in genres:
            vec[idx[g]] = 1.0
        for t, w in tagmap.items():
            vec[idx[t]] = max(vec[idx[t]], w)
        mat.append(vec)
        ids.append(mal_id)
    df = pd.DataFrame({"movie_id": ids, "feature_vector": list(np.array(mat))})
    return df, vocab


async def main(out: str = "model"):
    from pipelines.model_dev import ContentBasedFiltering, ItemBasedCF, UserBasedCF

    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    pool = await asyncpg.connect(DATABASE_URL)
    try:
        interactions = [dict(r) for r in await pool.fetch(
            "SELECT user_id, anime_id, status, score FROM user_anime_list")]
        catalog = [dict(r) for r in await pool.fetch(
            "SELECT mal_id, genres, tags_anilist, score FROM anime_catalog")]
    finally:
        await pool.close()

    if not catalog:
        raise SystemExit("anime_catalog is empty; crawl first (scripts/run_full_crawl.py)")

    ratings = status_frame(interactions)
    if ratings.empty:
        print("no interactions yet; writing popularity-only bundle", flush=True)
    else:
        matrix = ratings.pivot(index="user_id", columns="item_id",
                               values="rating")
        matrix.to_pickle(outdir / "user_item_matrix.pkl")

    feats, vocab = item_feature_frame(catalog)
    with open(outdir / "content_vocab.pkl", "wb") as f:
        pickle.dump(vocab, f)

    if not ratings.empty:
        user_cf, item_cf = UserBasedCF(), ItemBasedCF()
        user_cf.train(str(outdir / "user_item_matrix.pkl"))
        item_cf.train(str(outdir / "user_item_matrix.pkl"))
        with open(outdir / "user_cf.pkl", "wb") as f:
            pickle.dump(user_cf, f)
        with open(outdir / "item_cf.pkl", "wb") as f:
            pickle.dump(item_cf, f)
        print(f"cf matrices: users={len(matrix)} items={len(matrix.columns)}", flush=True)

    content = ContentBasedFiltering()
    content.train(feats, None)
    with open(outdir / "content_cf.pkl", "wb") as f:
        pickle.dump(content, f)

    pop = sorted(catalog,
                 key=lambda r: (-(r.get("score") or 0), -(r.get("mal_id") or 0)))
    with open(outdir / "popular.pkl", "wb") as f:
        pickle.dump([r["mal_id"] for r in pop], f)
    print(f"content items={len(feats)} popular={len(pop)} SAVED -> {outdir}", flush=True)


if __name__ == "__main__":
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "model"
    asyncio.run(main(out))
