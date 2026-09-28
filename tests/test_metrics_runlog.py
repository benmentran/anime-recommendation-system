"""Metrics + run_log units (no infra, no network)."""
import json
import sys

import pandas as pd

sys.path.insert(0, ".")

from pipelines import metrics as M
from pipelines.run_log import start_run


def test_precision_matches_benchmark_convention():
    assert M.precision_at_k([1, 2, 3, 4, 5], {1, 3}, 5) == 0.4
    assert M.precision_at_k([1, 2], {1}, 5) == 0.2  # /k, not /len
    assert M.precision_at_k([], {1}, 5) == 0.0
    assert M.precision_at_k([1], set(), 5) == 0.0


def test_recall_and_candidate_recall():
    assert M.recall_at_k([1, 2, 3], {1, 2, 9}, 3) == 2 / 3
    assert M.candidate_recall_at_n({1, 2}, {1, 2, 3}) == 2 / 3
    assert M.candidate_recall_at_n(set(), {1}) == 0.0
    assert M.candidate_recall_at_n({1}, set()) == 0.0


def test_ndcg_perfect_and_worst():
    assert M.ndcg_at_k([1, 2, 3], {1, 2, 3}, 3) == 1.0
    assert M.ndcg_at_k([9, 8, 7], {1, 2}, 3) == 0.0
    assert M.ndcg_at_k([2, 9, 1], {1, 2}, 2) < 1.0
    assert M.ndcg_at_k([1], set(), 3) == 0.0


def test_mrr_and_map():
    assert M.mrr([9, 1, 2], {1}) == 0.5
    assert M.mrr([9, 8], {1}) == 0.0
    assert M.map_at_k([1, 9, 2], {1, 2}, 3) == (1.0 + 2 / 3) / 2
    assert M.map_at_k([], {1}, 3) == 0.0


def test_run_log_manifest(tmp_path, monkeypatch):
    import pipelines.run_log as rl

    monkeypatch.setattr(rl, "ARTIFACTS", tmp_path)
    df = pd.DataFrame({"b": [2, 1], "a": ["y", "x"]})
    with start_run("demo", {"lr": 0.1}, data_source="simulated", seed=7) as ctx:
        ctx.log_metrics({"ndcg": 0.5})
        tbl = ctx.save_table("split", df)
        js = ctx.save_json("maps", {"u": [1]})
        assert tbl.exists() and js.exists()
    man = json.loads((ctx.dir / "manifest.json").read_text(encoding="utf-8"))
    for key in ("params", "metrics", "git_sha", "versions", "seed",
                "dataset_digest", "data_source", "start_time", "end_time", "files"):
        assert key in man, key
    assert man["data_source"] == "simulated" and man["seed"] == 7
    assert man["metrics"] == {"ndcg": 0.5}
    assert set(man["files"]) == {"split.parquet", "maps.json"}
    # digest stability: same frame -> same bytes
    again = ctx.dir / "again.parquet"
    df.sort_values(by=list(df.columns)).reset_index(drop=True).to_parquet(again, index=False)
    import hashlib

    assert hashlib.sha256(tbl.read_bytes()).hexdigest() == hashlib.sha256(
        again.read_bytes()).hexdigest()
