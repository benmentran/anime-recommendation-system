"""Ranking metrics for the two-stage recommender (pure numpy, no deps beyond it).

Conventions (shared with scripts/wsl_benchmark.py and scripts/score_loose.py):
- `ranked`: ordered list of item ids (best first).
- `rel`: set of relevant item ids.
- Empty relevance -> 0.0 (never NaN). k larger than the list is clipped.

Also `candidate_recall_at_n`: unordered recall for stage-1 candidate generation
(Recall@200) — the ceiling for the whole pipeline.
"""
from collections.abc import Collection, Sequence


def precision_at_k(ranked: Sequence[int], rel: Collection[int], k: int) -> float:
    """Fraction of top-k that is relevant (same convention as wsl_benchmark: /k)."""
    if k <= 0 or not set(rel):
        return 0.0
    relset = set(rel)
    return sum(1 for i in list(ranked)[:k] if i in relset) / k


def recall_at_k(ranked: Sequence[int], rel: Collection[int], k: int) -> float:
    """Fraction of relevant items retrieved in top-k."""
    relset = set(rel)
    if k <= 0 or not relset:
        return 0.0
    top = set(list(ranked)[:k])
    return len(top & relset) / len(relset)


def _dcg(gains: Sequence[float]) -> float:
    import math

    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked: Sequence[int], rel: Collection[int], k: int) -> float:
    """NDCG with binary gains (1 if relevant else 0)."""
    relset = set(rel)
    if k <= 0 or not relset:
        return 0.0
    top = list(ranked)[:k]
    dcg = _dcg([1.0 if i in relset else 0.0 for i in top])
    ideal = _dcg([1.0] * min(len(relset), len(top)))
    return dcg / ideal if ideal > 0 else 0.0


def mrr(ranked: Sequence[int], rel: Collection[int]) -> float:
    """Mean reciprocal rank of the first relevant item (single query -> RR)."""
    relset = set(rel)
    if not relset:
        return 0.0
    for i, item in enumerate(ranked):
        if item in relset:
            return 1.0 / (i + 1)
    return 0.0


def map_at_k(ranked: Sequence[int], rel: Collection[int], k: int) -> float:
    """Mean average precision at k (single query -> AP@k)."""
    relset = set(rel)
    if k <= 0 or not relset:
        return 0.0
    top = list(ranked)[:k]
    hits = 0
    total = 0.0
    for i, item in enumerate(top):
        if item in relset:
            hits += 1
            total += hits / (i + 1)
    return total / min(len(relset), k)


def candidate_recall_at_n(candidates: Collection[int],
                          ground_truth: Collection[int]) -> float:
    """Unordered recall of stage-1 candidates vs ground-truth set (Recall@200).

    Order-free: measures coverage only. This is the ceiling for stage 2 —
    whatever the ranker does, it cannot recover items missing here.
    """
    gt = set(ground_truth)
    if not gt:
        return 0.0
    return len(set(candidates) & gt) / len(gt)


def ranked_list_metrics(ranked: list[int], rel: Collection[int],
                        ks: Sequence[int] = (5, 10)) -> dict:
    """Convenience: P/R/NDCG at several k + MRR + MAP@max(ks) in one dict."""
    out = {"mrr": round(mrr(ranked, rel), 6)}
    for k in ks:
        out[f"precision@{k}"] = round(precision_at_k(ranked, rel, k), 6)
        out[f"recall@{k}"] = round(recall_at_k(ranked, rel, k), 6)
        out[f"ndcg@{k}"] = round(ndcg_at_k(ranked, rel, k), 6)
    out[f"map@{max(ks)}"] = round(map_at_k(ranked, rel, max(ks)), 6)
    return out
