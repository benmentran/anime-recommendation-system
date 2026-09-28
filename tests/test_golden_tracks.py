"""Golden tracks: split counts, RAGAS schema, behavior format preserved."""
import json
import sys

import pandas as pd

sys.path.insert(0, ".")

from scripts.build_golden_tracks import RAGAS_CATS
from scripts.build_golden_tracks import main as build_tracks

RAGAS_REQUIRED = ["id", "question", "reference", "reference_contexts"]
ORIGINAL_COLS = ["id", "category", "intent", "question", "expected_entities",
                 "expected_behavior", "difficulty", "notes"]


def _build(tmp_path):
    build_tracks(str(tmp_path))
    rag = pd.read_csv(tmp_path / "ragas_track.csv")
    beh = pd.read_csv(tmp_path / "behavior_track.csv")
    return rag, beh


def test_split_counts_and_no_overlap(tmp_path):
    rag, beh = _build(tmp_path)
    assert len(rag) == 30 and len(beh) == 21
    assert set(rag["id"]).isdisjoint(set(beh["id"]))
    assert set(rag["id"]) | set(beh["id"]) == set(range(1, 52))


def test_ragas_track_covers_factual_groups(tmp_path):
    rag, _ = _build(tmp_path)
    assert set(rag["category"]).issubset(RAGAS_CATS)
    for _, r in rag.iterrows():
        assert str(r["question"]).strip()
        ctxs = json.loads(r["reference_contexts"])
        if not r["needs_review"]:
            assert str(r["reference"]).strip(), f"empty reference id={r['id']}"
            assert isinstance(ctxs, list) and len(ctxs) > 0
            assert all("Title:" in c for c in ctxs)


def test_behavior_track_keeps_original_format_plus_rubric(tmp_path):
    _, beh = _build(tmp_path)
    for c in ORIGINAL_COLS:
        assert c in beh.columns, f"missing original column {c}"
    assert "rubric" in beh.columns and beh["rubric"].str.strip().ne("").all()


def test_only_context_dependent_row_flagged(tmp_path):
    rag, _ = _build(tmp_path)
    flagged = sorted(rag.loc[rag["needs_review"], "id"].tolist())
    assert flagged == [30]  # title=(ngữ cảnh trước đó): unresolvable standalone
