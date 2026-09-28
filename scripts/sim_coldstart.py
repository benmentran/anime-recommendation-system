"""Genre-archetype cold-start experiment (thin wrapper, no simulator logic).

All simulator logic lives in pipelines/simulation.py (taste seeding, choice,
drift, arms, metrics loop). This file only: loads the genre catalog, maps CLI
flags to simulation params, and reshapes results into the legacy JSON/table
(NDCG@5 + intent recall + per-archetype + rounds-to-0.3) used by the README.

KET QUA LA MO PHONG (simulated), khong phai user that.

Usage:
    python scripts/sim_coldstart.py [--users 1000] [--rounds 10] [--seed 7]
        [--temperature 0.1] [--drift 0.15] [--explore 2] [--alpha 0.7]
        [--catalog data/raw/anime_jikan.ndjson] [--out data/sim/coldstart.json]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from pipelines import simulation as S

THRESHOLD_NDCG = 0.3
ARCHES = ("single", "mix", "eclectic")


def run_legacy(n_users=1000, rounds=10, seed=7, temperature=0.1, drift=0.15,
               explore=2, hybrid_alpha=0.7, catalog="data/raw/anime_jikan.ndjson",
               p_single=0.25, p_mix=0.55):
    """Run the legacy 3-arm experiment via pipelines/simulation. Returns JSON-able dict."""
    rng = np.random.default_rng(seed)
    cat = S.item_vectors_from_catalog(catalog)
    names, V, members = cat["names"], cat["V"], cat["members"]
    print(f"catalog: {cat['n']} anime, {len(names)} genres")
    anchors, arch = S.seed_anchors_arch(rng, n_users, names, cat["counts"],
                                        p_single, p_mix)
    U0 = S.seed_tastes(rng, n_users, V.shape[1], anchors, arch, names,
                       cat["combos"])
    arms_all = S.build_arms(V, members, hybrid_alpha, switch_at=0)  # 0 = fixed blend
    arms = {k: arms_all[k] for k in ("popularity", "content", "hybrid")}
    params = {"seed": seed, "n_users": n_users, "slate_k": 5,
              "beta": 1.0 / temperature, "no_click_logit": 0.0,
              "alpha": drift, "drift_noise": 0.0, "explore_slots": explore,
              "hybrid_alpha": hybrid_alpha, "rank_k": 5,
              "ground_truth_topm": 50,
              "eval_steps": list(range(1, rounds + 1))}
    res = S.run_experiment(V, members, U0, arms, params,
                           np.random.default_rng(seed + 999),
                           groups=arch, return_slates=True)
    order = [s for s in sorted(res["curves"]["popularity"]["ndcg"]) if s != 0]
    curves, per_arch = {}, {a: {k: {"ndcg": [], "intent_recall": []} for k in ARCHES}
                            for a in arms}
    for name in arms:
        ndcg_list, ir_list = [], []
        for s in order:
            ndcg_list.append(round(res["curves"][name]["ndcg"][s], 4))
            sl = res["slates"][name][s]
            ir = float(np.mean([S.intent_recall_at_k(sl[i], U0[i], V)
                                for i in range(n_users)]))
            ir_list.append(round(ir, 4))
        curves[name] = {"ndcg": ndcg_list, "intent_recall": ir_list}
        for k in ARCHES:
            per_arch[name][k]["ndcg"] = [
                round(res["curves"][name].get(f"ndcg_{k}", {}).get(s, 0.0), 4)
                for s in order]
            m = arch == k
            per_arch[name][k]["intent_recall"] = [
                round(float(np.mean([S.intent_recall_at_k(res["slates"][name][s][i],
                                                          U0[i], V)
                                     for i in np.where(m)[0]])) if m.any() else 0.0, 4)
                for s in order]
    need = S.interactions_to_target(
        {a: {"ndcg": {s: v for s, v in res["curves"][a]["ndcg"].items() if s != 0}}
         for a in arms}, THRESHOLD_NDCG)
    summary = {a: {"rounds_to_ndcg03": need[a],
                   "ndcg_final": curves[a]["ndcg"][-1],
                   "intent_recall_final": curves[a]["intent_recall"][-1]}
               for a in arms}
    return {"curves": curves, "per_arch": per_arch, "summary": summary,
            "params": {"users": n_users, "rounds": rounds, "seed": seed,
                       "temperature": temperature, "drift": drift,
                       "explore_slots": explore, "hybrid_alpha": hybrid_alpha,
                       "simulated": True}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=1000)
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--drift", type=float, default=0.15)
    ap.add_argument("--explore", type=int, default=2)
    ap.add_argument("--alpha", type=float, default=0.7)
    ap.add_argument("--catalog", default="data/raw/anime_jikan.ndjson")
    ap.add_argument("--out", default="data/sim/coldstart.json")
    args = ap.parse_args()

    res = run_legacy(args.users, args.rounds, args.seed, args.temperature,
                     args.drift, args.explore, args.alpha, args.catalog)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(res, f, indent=1)
    print(f"{'arm':<12}{'rounds_to_NDCG0.3':<18}{'NDCG_final':<11}{'intent-recall_final'}")
    for a, s in res["summary"].items():
        hit = s["rounds_to_ndcg03"] or "never"
        print(f"{a:<12}{hit!s:<18}{s['ndcg_final']:<11}{s['intent_recall_final']}")
    print(f"saved -> {args.out} (SIMULATED, not real users)")


if __name__ == "__main__":
    main()
