"""Stage-1 candidate generation interface (two-stage recommender).

`generate_candidates(history, item_vecs, n, popularity=None) -> list[item_id]`:
baseline = user vector (mean of consumed item vectors, uniform prior when cold)
ranked by cosine, top-n. Excludes seen items.

Designed for swap: a future synopsis-embedding (Qdrant) implementation keeps
this exact signature, so simulator/metrics code does not change. Current
implementation is a genre/tag-vector baseline — see README (Evaluation).
"""
from collections.abc import Sequence

import numpy as np


def user_vector(history: Sequence[int], V: np.ndarray) -> np.ndarray:
    """Mean of consumed item vectors; flat prior when history is empty."""
    if not history:
        return np.full(V.shape[1], 1.0 / V.shape[1])
    return V[list(history)].mean(axis=0)


def generate_candidates(history: Sequence[int], V: np.ndarray, n: int = 200,
                        popularity: np.ndarray | None = None) -> list[int]:
    """Top-n candidate ids by cosine(user_vector, items), unseen only.

    Cold (empty history): flat prior -> all scores tie -> stable order by
    popularity when given, else index order. Deterministic.
    """
    u = user_vector(history, V)
    nu = np.linalg.norm(u) + 1e-12
    nv = np.linalg.norm(V, axis=1) + 1e-12
    scores = (V @ u) / (nv * nu)
    if popularity is not None and not history:
        pop = np.asarray(popularity, dtype=float)
        scores = (pop - pop.min()) / (pop.max() - pop.min() + 1e-9)
    scores[list(history)] = -np.inf
    order = np.argsort(-scores, kind="stable")
    return order[:n].tolist()
