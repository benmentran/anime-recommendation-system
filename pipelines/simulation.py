"""Pure numpy/pandas interaction simulator (replaces the RecSim draft).

Schema (kept): user_id, session_step, doc_id, click_prob, reward.
No heavy deps, no import-time side effects — Airflow/pytest import safely.
"""
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["user_id", "session_step", "doc_id", "click_prob", "reward"]
OUT = Path("data/simulation/synthetic_interactions.csv")


def simulate(num_users=100, num_docs=1000, num_episodes=50, slate_size=5,
             seed=42, tag_affinity=None):
    """Random-walk sessions with optional per-user tag affinity.

    tag_affinity: optional (num_users, n_tags) array biasing click_prob.
    Returns DataFrame with COLUMNS.
    """
    rng = np.random.default_rng(seed)
    user_aff = rng.normal(0, 1, num_users)  # base taste per user
    rows = []
    for _ in range(num_episodes):
        for u in range(num_users):
            drift = rng.normal(0, 0.1)  # interest drift per session
            docs = rng.choice(num_docs, size=slate_size, replace=False)
            for step, doc in enumerate(docs):
                bias = 0.0 if tag_affinity is None else float(
                    np.mean(tag_affinity[u % len(tag_affinity)]))
                click_prob = float(1 / (1 + np.exp(-(user_aff[u] + drift + bias))))
                reward = float(rng.random() < click_prob)
                rows.append((u, step, int(doc), click_prob, reward))
    return pd.DataFrame(rows, columns=COLUMNS)


def main(out_csv=str(OUT), **kwargs):
    df = simulate(**kwargs)
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(df.head())
    print(f"Synthetic data saved: {len(df)} interactions -> {out_csv}")
    return df


if __name__ == "__main__":
    main()
