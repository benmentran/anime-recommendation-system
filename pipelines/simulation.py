"""Ground-truth cold-start simulator, numpy only (RecSim ideas, no RecSim).

Every user hides a TRUE taste vector u (unit norm). Each step an arm proposes a
slate of K items, the user picks via softmax(beta * <u, v>) with a fixed-logit
no-click option, then u drifts toward the consumed item. Scoring always uses the
FROZEN initial taste u0, so an arm cannot inflate its score by steering the user.

All outputs are labeled data_source="simulated" and must never be mixed with
real-user metrics.

Arms are pluggable `recommend(uid, history, k, world)` callables; the shared
`world` dict carries logs, popularity and CF state. Two-stage story: stage-1
`generate_candidates` (pipelines/candidates.py) -> stage-2 arm ranking.

Usage:
    python pipelines/simulation.py [--catalog data/raw/anime_jikan.ndjson]
        [--out data/sim/coldstart_v2.json] [--run-log]
Deps: numpy, pandas, pyarrow (run_log). No mlflow/dvc/recsim.
"""
import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

RecommendFn = Callable[[int, list[int], int, dict], list[int]]

INTENT_MIN_W = 0.2


def load_params(path: str = "params.yaml") -> dict:
    """Read the pipelines.simulation section (defaults when file/keys missing)."""
    defaults = {
        "seed": 7, "n_users": 1000, "steps": 20, "slate_k": 5, "beta": 10.0,
        "no_click_logit": 0.0, "alpha": 0.05, "drift_noise": 0.0,
        "explore_slots": 2, "hybrid_alpha": 0.7, "hybrid_switch_at": 5,
        "ndcg_target": 0.3, "candidate_n": 200, "rating_a": 5.5,
        "rating_b": 4.5, "rating_noise": 0.5, "ground_truth_topm": 50,
        "eval_steps": [0, 1, 2, 3, 5, 10, 20], "p_single": 0.25, "p_mix": 0.55,
    }
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        defaults.update((cfg.get("pipelines") or {}).get("simulation") or {})
    except Exception:  # noqa: BLE001,S110 - optional config, defaults apply
        pass
    return defaults


def l2_normalize_rows(M: np.ndarray) -> np.ndarray:
    """L2-normalize rows; zero rows stay zero."""
    n = np.linalg.norm(M, axis=1, keepdims=True)
    return np.divide(M, n, out=np.zeros_like(M, dtype=float), where=n > 0)


def item_vectors_from_catalog(path: str) -> dict:
    """NDJSON Tenrai/Jikan-schema -> L2 genre rows + members + combos + counts."""
    import json as _json

    names: list[str] = []
    gindex: dict[str, int] = {}
    rows: list[list] = []
    members: list[float] = []
    combos: list[list] = []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        d = _json.loads(line).get("data", {})
        gs = [x["name"] for x in (d.get("genres") or []) if x.get("name")]
        for gname in gs:
            if gname not in gindex:
                gindex[gname] = len(names)
                names.append(gname)
        rows.append(gs)
        try:
            members.append(int(d.get("members") or 0))
        except (TypeError, ValueError):
            members.append(0)
        if 2 <= len(set(gs)) <= 3:
            combos.append(sorted(set(gs)))
    V = np.zeros((len(rows), len(names)))
    for i, gs in enumerate(rows):
        for gname in set(gs):
            V[i, gindex[gname]] = 1.0
    V = l2_normalize_rows(V)
    counts = {gname: int((V[:, j] > 0).sum()) for j, gname in enumerate(names)}
    return {"names": names, "V": V, "members": np.array(members, dtype=float),
            "counts": counts, "combos": combos, "n": len(rows)}


def synthetic_clustered_vectors(rng: np.random.Generator, n_items: int = 500,
                                d: int = 21, n_clusters: int = 6) -> dict:
    """Fallback item vectors when no catalog is available (logic stays testable)."""
    cents = l2_normalize_rows(rng.normal(size=(n_clusters, d)))
    assign = rng.integers(0, n_clusters, n_items)
    V = l2_normalize_rows(cents[assign] + 0.3 * rng.normal(size=(n_items, d)))
    return {"names": [f"dim{i}" for i in range(d)], "V": V,
            "members": rng.integers(10, 10000, n_items).astype(float),
            "counts": {}, "combos": [], "n": n_items}


def seed_tastes(rng: np.random.Generator, n_users: int, n_dims: int,
                anchors: Sequence[int], arch: Sequence[str],
                names: Sequence[str], combos: Sequence[Sequence[str]]) -> np.ndarray:
    """Ground-truth tastes: unit-norm mixtures of 1-3 genre clusters.

    single: ~0.85 anchor + Dirichlet noise; mix: real catalog 2-3 combo mean;
    eclectic: flat Dirichlet. Output rows are UNIT vectors (spec), not simplex.
    """
    gindex = {gname: j for j, gname in enumerate(names)}
    combo_idx = [[gindex[gname] for gname in c] for c in combos]
    by_anchor: dict[int, list] = {}
    for k, idxs in enumerate(combo_idx):
        for j in idxs:
            by_anchor.setdefault(j, []).append(k)
    U = np.zeros((n_users, n_dims))
    for i in range(n_users):
        a = int(anchors[i])
        kind = arch[i]
        if kind == "single":
            vec = 0.15 * rng.dirichlet(np.full(n_dims, 0.5))
            vec[a] += 0.85
        elif kind == "mix" and combo_idx:
            pool = by_anchor.get(a) or list(range(len(combo_idx)))
            vec = np.zeros(n_dims)
            for j in combo_idx[rng.choice(pool)]:
                vec[j] = 1.0
            vec = vec / vec.sum()
            vec = 0.7 * vec + 0.3 * rng.dirichlet(np.full(n_dims, 0.5))
        else:
            vec = rng.dirichlet(np.full(n_dims, 2.0))
        U[i] = vec / (np.linalg.norm(vec) + 1e-12)
    return U


def seed_anchors_arch(rng: np.random.Generator, n_users: int, names: Sequence[str],
                      counts: dict, p_single: float = 0.25, p_mix: float = 0.55,
                      floor: int = 15) -> tuple:
    """Anchor genre per user (floor/genre + remainder proportional to catalog)."""
    G = len(names)
    rest = max(0, n_users - floor * G)
    tot = sum(counts.values()) if counts else 0
    anchors = []
    for j, gname in enumerate(names):
        k = floor + (round(rest * counts[gname] / tot) if tot else 0)
        anchors += [j] * k
    anchors = np.array(anchors)
    if len(anchors) < n_users:
        top = int(np.argmax([counts.get(gname, 0) for gname in names])) if counts else 0
        anchors = np.concatenate([anchors, np.full(n_users - len(anchors), top)])
    anchors = rng.permutation(anchors[:n_users])
    u = rng.random(n_users)
    arch = np.where(u < p_single, "single",
                    np.where(u < p_single + p_mix, "mix", "eclectic"))
    return anchors, arch


def softmax_choice(rng: np.random.Generator, dots: np.ndarray, beta: float,
                   no_click_logit: float = 0.0) -> int | None:
    """Pick a slate position (or None = no-click) from taste-item dots.

    P(i) = softmax([beta*dots, no_click_logit]). Probabilities sum to 1.
    """
    logits = np.append(beta * np.asarray(dots, dtype=float), no_click_logit)
    logits -= logits.max()
    p = np.exp(logits)
    p /= p.sum()
    pos = int(rng.choice(len(p), p=p))
    return pos if pos < len(dots) else None


def evolve_taste(u: np.ndarray, v: np.ndarray, alpha: float,
                 noise: float = 0.0,
                 rng: np.random.Generator | None = None) -> np.ndarray:
    """Interest evolution: u <- normalize(u + alpha*(v - u) + noise). Unit norm kept."""
    step = u + alpha * (v - u)
    if noise > 0 and rng is not None:
        step = step + rng.normal(0, noise, size=u.shape)
    n = np.linalg.norm(step)
    return step / n if n > 0 else u


def simulate_score(rng: np.random.Generator, dot: float, a: float = 5.5,
                   b: float = 4.5, noise: float = 0.5) -> int:
    """Rating 1..10 from taste-item affinity."""
    return int(min(10, max(1, round(a + b * dot + rng.normal(0, noise)))))


def ground_truth_top(u: np.ndarray, V: np.ndarray, m: int = 50) -> list[int]:
    """Top-m item ids by <u, v> — the relevance oracle for metrics."""
    return np.argsort(-(V @ u))[:m].tolist()


def graded_ndcg(ranked: Sequence[int], dots: np.ndarray, k: int) -> float:
    """NDCG with continuous relevance (dots = V @ u0). Ideal = top-k dots.

    Binary top-m relevance punishes taste drift brutally (drifted slate keeps
    high dots vs u0 but misses the exact top-m ids); graded relevance measures
    "right neighborhood", matching the legacy experiment semantics.
    """
    rel = np.asarray(dots)[list(ranked)[:k]]
    denom = np.log2(np.arange(2, 2 + len(rel)))
    dcg = float(np.sum(rel / denom))
    ideal = np.sort(np.asarray(dots))[::-1][: len(rel)]
    idcg = float(np.sum(ideal / denom))
    return dcg / idcg if idcg > 0 else 0.0


def intent_recall_at_k(slate: Sequence[int], taste: np.ndarray,
                       V: np.ndarray, min_w: float = INTENT_MIN_W) -> float:
    """Fraction of taste intents (dims with weight >= min_w, else top-3) hit by slate."""
    intents = np.where(taste >= min_w)[0]
    if len(intents) == 0:
        intents = np.argsort(-taste)[:3]
    hits = sum(bool((V[list(slate)][:, g] > 0).any()) for g in intents)
    return hits / len(intents)


class PopularityArm:
    """Static popularity ranking (cold-start round-0 fallback)."""

    def __init__(self, members: np.ndarray):
        pop = np.log1p(np.asarray(members, dtype=float))
        self.scores = (pop - pop.min()) / (pop.max() - pop.min() + 1e-9)

    def recommend(self, uid: int, history: list[int], k: int, world: dict) -> list[int]:
        s = self.scores.copy()
        s[history] = -np.inf
        return np.argsort(-s, kind="stable")[:k].tolist()


class ContentArm:
    """User vector = mean of consumed item vectors (uniform prior).

    Single-experiment state: call reset() (done automatically by
    run_experiment) before reuse, or stale estimates leak across runs.
    """

    def __init__(self, V: np.ndarray):
        self.V = V
        self.est: dict[int, np.ndarray] = {}

    def reset(self) -> None:
        self.est.clear()

    def _est(self, uid: int, history: list[int]) -> np.ndarray:
        if not history:
            return np.full(self.V.shape[1], 1.0 / self.V.shape[1])
        if uid not in self.est:
            self.est[uid] = self.V[history].mean(axis=0)
        return self.est[uid]

    def observe(self, uid: int, item: int) -> None:
        self.est.pop(uid, None)  # recompute lazily from history

    def recommend(self, uid: int, history: list[int], k: int, world: dict) -> list[int]:
        s = self.V @ self._est(uid, history)
        s = (s - s.min()) / (s.max() - s.min() + 1e-9)
        s[list(history)] = -np.inf
        return np.argsort(-s, kind="stable")[:k].tolist()


class CFArm:
    """User-based CF on the accumulated simulated log (cosine, neighbor-weighted).

    Empty history / no neighbors -> popularity fallback (honest cold-start).
    """

    def __init__(self, members: np.ndarray):
        self.pop = PopularityArm(members)

    def recommend(self, uid: int, history: list[int], k: int, world: dict) -> list[int]:
        import pandas as pd

        logs = world.get("logs")
        if logs is None or len(logs) == 0 or not history:
            return self.pop.recommend(uid, history, k, world)
        mat = pd.crosstab(logs["user_id"], logs["item_id"]).reindex(
            columns=world["item_ids"], fill_value=0).to_numpy(dtype=float)
        if uid >= len(mat) or mat[uid].sum() == 0:
            return self.pop.recommend(uid, history, k, world)
        n = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12
        sim = (mat @ mat[uid]) / (n[:, 0] * n[uid, 0])
        sim[uid] = 0.0
        if (sim <= 0).all():
            return self.pop.recommend(uid, history, k, world)
        scores = sim @ mat
        scores[list(history)] = -np.inf
        return np.argsort(-scores, kind="stable")[:k].tolist()


class HybridSwitchArm:
    """Content-based until len(history) >= threshold, then alpha-blend with CF."""

    def __init__(self, content: ContentArm, cf: CFArm, alpha: float = 0.7,
                 switch_at: int = 5, n_items: int = 0):
        self.content = content
        self.cf = cf
        self.alpha = alpha
        self.switch_at = switch_at
        self.n = n_items

    def reset(self) -> None:
        for arm in (self.content, self.cf):
            reset = getattr(arm, "reset", None)
            if callable(reset):
                reset()

    def _scores(self, arm, uid, history) -> np.ndarray:
        order = arm.recommend(uid, history, self.n, {})
        s = np.zeros(self.n)
        s[order] = 1.0 / (np.arange(len(order)) + 1)  # rank-reciprocal, normalized below
        return s / (s.max() + 1e-9)

    def recommend(self, uid: int, history: list[int], k: int, world: dict) -> list[int]:
        if len(history) < self.switch_at:
            return self.content.recommend(uid, history, k, world)
        s = self.alpha * self._scores(self.content, uid, history) + \
            (1 - self.alpha) * self._scores(self.cf, uid, history)
        s[list(history)] = -np.inf
        return np.argsort(-s, kind="stable")[:k].tolist()


def build_arms(V: np.ndarray, members: np.ndarray, alpha: float = 0.7,
               switch_at: int = 5) -> dict[str, object]:
    """The four cold-start strategies: popularity / content / CF / hybrid-switch."""
    content = ContentArm(V)
    cf = CFArm(members)
    return {
        "popularity": PopularityArm(members),
        "content": content,
        "cf": cf,
        "hybrid": HybridSwitchArm(content, cf, alpha, switch_at, V.shape[0]),
    }


def run_experiment(V: np.ndarray, members: np.ndarray, U0: np.ndarray,
                   arms: dict[str, object], params: dict,
                   rng: np.random.Generator | None = None,
                   groups: np.ndarray | None = None,
                   return_slates: bool = False) -> dict:
    """Cold-start loop. Returns curves/logs/tastes (all simulated).

    Per step: rank top-rank_k for metrics -> slate top-K (+explore slots) for
    interaction -> choice (no-click possible) -> drift + rating + log.
    Metrics at eval_steps vs FROZEN U0 and ground-truth top-m.
    groups: optional per-user labels -> per-group metric means.
    return_slates: also return slates[arm][step] (n_users, K) for wrappers.
    """
    from pipelines.metrics import recall_at_k

    p = params
    rng = rng or np.random.default_rng(p.get("seed", 7))
    n_users = U0.shape[0]
    n_items = V.shape[0]
    K = int(p.get("slate_k", 5))
    steps = sorted(set([0] + [int(s) for s in p.get("eval_steps", [0])]))
    max_step = max(steps)
    m = int(p.get("ground_truth_topm", 50))

    for arm in arms.values():
        reset = getattr(arm, "reset", None)
        if callable(reset):
            reset()
    U = U0.copy()
    histories: list[list[int]] = [[] for _ in range(n_users)]
    logs: list[dict] = []
    gt = [set(ground_truth_top(U0[i], V, m)) for i in range(n_users)]
    rank_k = int(p.get("rank_k", 10))
    curves = {a: {"ndcg": {}, "recall": {}, "cand_recall": {}} for a in arms}
    if groups is not None:
        for a in arms:
            for glabel in sorted(set(groups.tolist())):
                curves[a][f"ndcg_{glabel}"] = {}
    slates: dict[str, dict] = {a: {} for a in arms} if return_slates else {}
    cand_fn = None
    try:
        from pipelines.candidates import generate_candidates
        cand_fn = generate_candidates
    except ImportError:  # candidates module unavailable -> skip stage-1 recall
        cand_fn = None

    def measure(step: int):
        import pandas as pd

        world = {"logs": pd.DataFrame(logs) if logs else pd.DataFrame(
            columns=["user_id", "item_id", "clicked", "score", "step"]),
            "item_ids": list(range(n_items))}
        for name, arm in arms.items():
            ndcgs, recs, crecs = [], [], []
            per_g: dict[str, list] = {}
            dots_all = V @ U0.T  # (items, users): frozen graded relevance
            for i in range(n_users):
                ranked = arm.recommend(i, histories[i], rank_k, world)[:rank_k]
                v = graded_ndcg(ranked, dots_all[:, i], rank_k)
                ndcgs.append(v)
                recs.append(recall_at_k(ranked, gt[i], rank_k))
                if groups is not None:
                    per_g.setdefault(str(groups[i]), []).append(v)
                if cand_fn is not None:
                    from pipelines.metrics import candidate_recall_at_n
                    cands = cand_fn(histories[i], V,
                                    int(p.get("candidate_n", 200)), members)
                    crecs.append(candidate_recall_at_n(set(cands), gt[i]))
            curves[name]["ndcg"][step] = float(np.mean(ndcgs))
            curves[name]["recall"][step] = float(np.mean(recs))
            for glabel, vals in per_g.items():
                curves[name][f"ndcg_{glabel}"][step] = float(np.mean(vals))
            if crecs:
                curves[name]["cand_recall"][step] = float(np.mean(crecs))

    measure(0)
    for step in range(1, max_step + 1):
        import pandas as pd

        world = {"logs": pd.DataFrame(logs) if logs else pd.DataFrame(
            columns=["user_id", "item_id", "clicked", "score", "step"]),
            "item_ids": list(range(n_items))}
        for name, arm in arms.items():
            n_exp = int(p.get("explore_slots", 2)) if name != "popularity" else 0
            step_slates = np.zeros((n_users, K), dtype=int) if return_slates else None
            for i in range(n_users):
                base = arm.recommend(i, histories[i], K, world)[:K]
                slate = list(base)
                if n_exp and len(histories[i]) < n_items:
                    pool = np.array([x for x in range(n_items)
                                     if x not in histories[i] and x not in slate])
                    if len(pool):
                        extra = rng.choice(pool, min(n_exp, len(pool)), replace=False)
                        slate = base[:K - len(extra)] + extra.tolist()
                if step_slates is not None:
                    step_slates[i] = slate
                dots = V[slate] @ U[i]
                pos = softmax_choice(rng, dots, float(p.get("beta", 10.0)),
                                     float(p.get("no_click_logit", 0.0)))
                if pos is None:
                    continue  # no-click: no drift, no log
                item = slate[pos]
                histories[i].append(item)
                U[i] = evolve_taste(U[i], V[item], float(p.get("alpha", 0.05)),
                                    float(p.get("drift_noise", 0.0)), rng)
                score = simulate_score(rng, float(V[item] @ U0[i]),
                                       float(p.get("rating_a", 5.5)),
                                       float(p.get("rating_b", 4.5)),
                                       float(p.get("rating_noise", 0.5)))
                logs.append({"user_id": i, "item_id": item, "clicked": 1,
                             "score": score, "step": step})
                obs = getattr(arm, "observe", None)
                if callable(obs):
                    obs(i, item)
                inner = getattr(arm, "content", None)
                if inner is not None and hasattr(inner, "observe"):
                    inner.observe(i, item)
            if step_slates is not None and step in steps:
                slates[name][step] = step_slates
        if step in steps:
            measure(step)
    import pandas as pd

    out = {"curves": curves,
           "logs": pd.DataFrame(logs, columns=["user_id", "item_id", "clicked",
                                               "score", "step"]),
           "tastes0": U0, "params": dict(p)}
    out["params"]["simulated"] = True
    if return_slates:
        out["slates"] = slates
    return out


def interactions_to_target(curves: dict, target: float = 0.3) -> dict:
    """Steps needed per arm to reach NDCG >= target (None = never)."""
    out = {}
    for name, c in curves.items():
        hit = next((s for s in sorted(c["ndcg"]) if c["ndcg"][s] >= target), None)
        out[name] = hit
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="data/raw/anime_jikan.ndjson")
    ap.add_argument("--out", default="data/sim/coldstart_v2.json")
    ap.add_argument("--run-log", action="store_true")
    ap.add_argument("--users", type=int, default=None)
    ap.add_argument("--steps", type=int, default=None)
    args = ap.parse_args()

    params = load_params()
    if args.users:
        params["n_users"] = args.users
    if args.steps:
        params["steps"] = args.steps
        params["eval_steps"] = sorted(set([0] + list(range(1, args.steps + 1))))
    rng = np.random.default_rng(params["seed"])
    try:
        cat = item_vectors_from_catalog(args.catalog)
    except (OSError, ValueError):
        cat = synthetic_clustered_vectors(rng)
    names, V, members = cat["names"], cat["V"], cat["members"]
    anchors, arch = seed_anchors_arch(rng, params["n_users"], names,
                                      cat.get("counts") or {}, params["p_single"],
                                      params["p_mix"])
    U0 = seed_tastes(rng, params["n_users"], V.shape[1], anchors, arch,
                     names, cat.get("combos") or [])
    arms = build_arms(V, members, params["hybrid_alpha"], params["hybrid_switch_at"])
    res = run_experiment(V, members, U0, arms, params, rng)
    need = interactions_to_target(res["curves"], params["ndcg_target"])

    rk = int(params.get("rank_k", 10))
    serial = {a: {"steps_to_target": need[a],
                  f"ndcg@{rk}": {str(s): round(v, 4) for s, v in c["ndcg"].items()},
                  f"recall@{rk}": {str(s): round(v, 4) for s, v in c["recall"].items()},
                  "cand_recall": {str(s): round(v, 4)
                                  for s, v in c.get("cand_recall", {}).items()}}
              for a, c in res["curves"].items()}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({"arms": serial, "params": res["params"]}, f, indent=1)
    print(f"{'arm':<12}{'steps_to_NDCG':<16}{f'NDCG@{rk} final':<14}{f'Recall@{rk} final'}")
    for a, s in serial.items():
        last = max(res["curves"][a]["ndcg"])
        print(f"{a:<12}{s['steps_to_target']!s:<16}"
              f"{s[f'ndcg@{rk}'][str(last)]:<14}{s[f'recall@{rk}'][str(last)]}")
    print(f"saved -> {args.out} (SIMULATED, not real users)")
    if args.run_log:
        from pipelines.run_log import start_run

        with start_run("simulation", params, data_source="simulated",
                       seed=params["seed"]) as ctx:
            ctx.save_table("logs", res["logs"])
            ctx.save_table("tastes0",
                           __import__("pandas").DataFrame(res["tastes0"]))
            ctx.log_metrics({f"{a}_steps_to_target": (v if v is not None else -1)
                             for a, v in need.items()})
            ctx.save_json("curves", serial)


if __name__ == "__main__":
    sys.path.insert(0, ".")
    main()
