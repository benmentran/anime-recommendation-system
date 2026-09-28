"""PART B: simulation units — choice, evolution, determinism, manifest (no infra)."""
import sys

import numpy as np

sys.path.insert(0, ".")

from pipelines import simulation as S
from pipelines.candidates import generate_candidates


def _tiny():
    rng = np.random.default_rng(0)
    cat = S.synthetic_clustered_vectors(rng, n_items=60, d=8, n_clusters=3)
    return cat


def test_choice_probabilities_sum_to_one():
    rng = np.random.default_rng(1)
    dots = np.array([0.9, 0.2, 0.1, 0.0, -0.3])
    counts = np.zeros(6)  # 5 items + no-click
    for _ in range(20000):
        pos = S.softmax_choice(rng, dots, beta=1.0, no_click_logit=0.0)
        counts[pos if pos is not None else 5] += 1
    p = counts / counts.sum()
    assert abs(p.sum() - 1.0) < 1e-9
    assert p[0] > p[1] > p[4] > 0  # higher affinity chosen more often
    assert p[5] > 0.05  # no-click reachable (logit 0 vs weak dots)
    # no-click dominates when everything is bad
    rng2 = np.random.default_rng(2)
    seen_none = sum(S.softmax_choice(rng2, np.full(5, -5.0), beta=1.0,
                                     no_click_logit=5.0) is None
                    for _ in range(200))
    assert seen_none > 150


def test_evolution_keeps_unit_norm():
    rng = np.random.default_rng(2)
    u = np.ones(8) / np.sqrt(8)
    v = np.zeros(8)
    v[0] = 1.0
    for _ in range(50):
        u = S.evolve_taste(u, v, alpha=0.05, noise=0.01, rng=rng)
        assert abs(np.linalg.norm(u) - 1.0) < 1e-9
    assert u[0] > 1 / np.sqrt(8)  # drifted toward consumed item


def test_seed_tastes_unit_norm_and_mixture():
    rng = np.random.default_rng(3)
    cat = _tiny()
    G = cat["V"].shape[1]
    anchors, arch = S.seed_anchors_arch(rng, 200, cat["names"], {}, 0.25, 0.55)
    U = S.seed_tastes(rng, 200, G, anchors, arch, cat["names"], [])
    assert U.shape == (200, G)
    assert np.allclose(np.linalg.norm(U, axis=1), 1.0)


def test_same_seed_identical_logs():
    cat = _tiny()
    params = S.load_params()
    params.update({"n_users": 20, "eval_steps": [0, 1, 2], "candidate_n": 30,
                   "seed": 11})
    arms = S.build_arms(cat["V"], cat["members"])
    r1 = S.run_experiment(cat["V"], cat["members"],
                          S.seed_tastes(np.random.default_rng(11), 20,
                                        cat["V"].shape[1],
                                        *S.seed_anchors_arch(
                                            np.random.default_rng(11), 20,
                                            cat["names"], {}, 0.25, 0.55)[:2],
                                        cat["names"], []),
                          arms, params, np.random.default_rng(11))
    r2 = S.run_experiment(cat["V"], cat["members"],
                          S.seed_tastes(np.random.default_rng(11), 20,
                                        cat["V"].shape[1],
                                        *S.seed_anchors_arch(
                                            np.random.default_rng(11), 20,
                                            cat["names"], {}, 0.25, 0.55)[:2],
                                        cat["names"], []),
                          arms, params, np.random.default_rng(11))
    assert r1["logs"].equals(r2["logs"])
    assert list(r1["logs"].columns) == ["user_id", "item_id", "clicked",
                                       "score", "step"]
    assert r1["logs"]["score"].between(1, 10).all()


def test_cf_arm_falls_back_when_cold():
    cat = _tiny()
    arm = S.CFArm(cat["members"])
    world = {"logs": None, "item_ids": list(range(cat["n"]))}
    recs = arm.recommend(0, [], 5, world)
    assert len(recs) == 5  # popularity fallback, no crash


def test_candidates_cover_and_exclude_seen():
    rng = np.random.default_rng(4)
    V = S.l2_normalize_rows(np.abs(rng.normal(size=(50, 8))))
    cands = generate_candidates([1, 2, 3], V, n=10)
    assert len(cands) == 10 and not ({1, 2, 3} & set(cands))
    cold = generate_candidates([], V, n=10, popularity=np.arange(50))
    assert cold[0] == 49  # cold -> popularity order


def test_run_log_manifest_simulated(tmp_path, monkeypatch):
    import pipelines.run_log as rl

    monkeypatch.setattr(rl, "ARTIFACTS", tmp_path)
    from pipelines.run_log import start_run

    with start_run("simulation", {"seed": 7}, data_source="simulated",
                   seed=7) as ctx:
        ctx.log_metrics({"popularity_steps_to_target": -1})
    import json

    man = json.loads((ctx.dir / "manifest.json").read_text(encoding="utf-8"))
    assert man["data_source"] == "simulated"
    assert man["params"] == {"seed": 7}
