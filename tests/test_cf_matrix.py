"""PART A: cf_matrix pure units on a tiny synthetic frame (no DB)."""
import sys

import pandas as pd

sys.path.insert(0, ".")

from pipelines.cf_matrix import (
    build_id_maps,
    filter_min_count,
    matrix_stats,
    time_split,
    to_sparse,
)
from pipelines.ingest_user_scores import (
    fuzzy_to_ts,
    normalize_score,
    parse_entries,
)


def _frame():
    rows = []
    # 3 users x 6 items, scores 1..10, monthly stamps
    for u in ("a", "b", "c"):
        for i, (aid, s) in enumerate([(1, 9), (2, 8), (3, 7), (4, 4), (5, 2), (6, 10)]):
            rows.append({"user_id": u, "anime_id": aid, "score": s,
                         "scored_at": pd.Timestamp(f"2026-0{1 + (i % 3)}-01")})
    return pd.DataFrame(rows)


def test_filter_drops_rare():
    df = _frame()
    extra = pd.DataFrame([{"user_id": "z", "anime_id": 99, "score": 9,
                           "scored_at": pd.Timestamp("2026-01-01")}])
    out = filter_min_count(pd.concat([df, extra], ignore_index=True), 2, 2)
    assert "z" not in set(out["user_id"]) and 99 not in set(out["anime_id"])
    assert len(out) == len(df)


def test_time_split_no_leakage():
    df = _frame()
    train, test = time_split(df, 0.2)
    assert len(test) == 3  # 1 per user (round(6*.2)=1)
    for u in ("a", "b", "c"):
        tr = train[train.user_id == u]
        te = test[test.user_id == u]
        assert len(tr) == 5 and len(te) == 1
        # test is the LATEST per user (sort scored_at, anime_id) -> no leakage
        assert te["scored_at"].min() >= tr["scored_at"].max()
    assert set(train["split"]) == {"train"} and set(test["split"]) == {"test"}


def test_implicit_binarization_and_shapes():
    df = _frame()
    uidx = {"a": 0, "b": 1, "c": 2}
    iidx = {a: a - 1 for a in range(1, 7)}
    exp = to_sparse(df, uidx, iidx)
    imp = to_sparse(df, uidx, iidx, implicit=True, threshold=7)
    assert exp.shape == imp.shape == (3, 6)
    assert set(imp.data.tolist()) <= {0.0, 1.0}
    assert int((exp.data >= 7).sum()) == int(imp.data.sum()) == 12  # 4/user x3
    st = matrix_stats(imp)
    assert st == {"n_users": 3, "n_items": 6, "nnz": 18,
                  "density": round(18 / 18, 8)}


def test_id_map_round_trip():
    m = build_id_maps(["u2", "u1", "u2"])
    assert m["idx_to_id"] == ["u1", "u2"]
    assert m["id_to_idx"] == {"u1": 0, "u2": 1}
    import json

    json.dumps(m)  # serializable


def test_digest_stability(tmp_path):
    import pipelines.run_log as rl
    from pipelines.run_log import sha256_file, start_run

    rl.ARTIFACTS = tmp_path
    df = _frame()
    with start_run("t", {}, data_source="simulated", seed=1) as ctx:
        p1 = ctx.save_table("s", df)
        d1 = ctx.set_dataset_file(p1)
    with start_run("t", {}, data_source="simulated", seed=1) as ctx:
        p2 = ctx.save_table("s", df.iloc[::-1])  # shuffled input
        d2 = ctx.set_dataset_file(p2)
    assert d1 == d2
    assert sha256_file(p1) == sha256_file(p2)


def test_normalize_score_formats():
    assert normalize_score(85, "POINT_100") == 8
    assert normalize_score(8.6, "POINT_10_DECIMAL") == 9
    assert normalize_score(7, "POINT_10") == 7
    assert normalize_score(4, "POINT_5") == 8
    assert normalize_score(3, "POINT_3") == 10
    assert normalize_score(0, "POINT_10") is None
    assert normalize_score(None, "POINT_100") is None
    assert normalize_score(11, "POINT_10") is None


def test_fuzzy_to_ts():
    import datetime as _dt

    assert fuzzy_to_ts({"year": 2020, "month": 3, "day": 5}, "X") == _dt.date(2020, 3, 5)
    assert fuzzy_to_ts({"year": 2020, "month": None, "day": None}, "X") == _dt.date(2020, 1, 1)
    assert fuzzy_to_ts({"year": None}, "2026-09-28") == _dt.date(2026, 9, 28)
    assert fuzzy_to_ts(None, _dt.date(2026, 9, 28)) == _dt.date(2026, 9, 28)


def test_parse_entries_skips_bad():
    payload = {"data": {"MediaListCollection": {"lists": [{"entries": [
        {"media": {"idMal": 1}, "score": 80,
         "completedAt": {"year": 2021, "month": 5, "day": 1}},
        {"media": {"idMal": None}, "score": 90, "completedAt": None},
        {"media": {"idMal": 2}, "score": 0, "completedAt": None},
        {"media": {"idMal": 3}, "score": 90,
         "completedAt": {"year": None, "month": None, "day": None}},
    ]}]}}}
    import datetime as _dt

    rows = parse_entries(payload, "u", "POINT_100", "2026-09-28")
    assert [(r["anime_id"], r["score"], r["scored_at"]) for r in rows] == [
        (1, 8, _dt.date(2021, 5, 1)), (3, 9, _dt.date(2026, 9, 28))]
