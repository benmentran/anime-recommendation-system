"""Thin-wrapper sim_coldstart: delegates to pipelines/simulation (no local logic)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from pipelines import simulation as S
from scripts.sim_coldstart import run_legacy


def test_genre_space_21():
    cat = S.item_vectors_from_catalog("data/raw/anime_jikan.ndjson")
    assert len(cat["names"]) == 21
    assert cat["V"].shape[1] == 21
    assert np.allclose(np.linalg.norm(cat["V"][cat["V"].sum(1) > 0], axis=1), 1.0)


def test_wrapper_has_no_simulator_logic():
    import scripts.sim_coldstart as w

    src = Path(w.__file__).read_text(encoding="utf-8")
    for token in ("argpartition", "softmax", "dirichlet", "def seed_tastes",
                  "def load_catalog", "def run_simulation"):
        assert token not in src, token


def test_legacy_smoke():
    res = run_legacy(n_users=60, rounds=3, catalog="data/raw/anime_jikan.ndjson")
    assert set(res["curves"]) == {"popularity", "content", "hybrid"}
    for a in ("popularity", "content", "hybrid"):
        assert len(res["curves"][a]["ndcg"]) == 3
        assert all(0.0 <= v <= 1.0 for v in res["curves"][a]["ndcg"])
        assert all(0.0 <= v <= 1.0 for v in res["curves"][a]["intent_recall"])
        s = res["summary"][a]
        assert s["rounds_to_ndcg03"] is None or 1 <= s["rounds_to_ndcg03"] <= 3
    assert res["params"]["simulated"] is True
