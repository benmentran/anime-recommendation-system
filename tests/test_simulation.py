"""Simulation rewrite: numpy/pandas only, schema kept, no import-time run."""
import sys

sys.path.insert(0, ".")


def test_simulate_schema_and_bounds():
    from pipelines import simulation as sim

    df = sim.simulate(num_users=4, num_docs=20, num_episodes=2, slate_size=3, seed=7)
    assert list(df.columns) == ["user_id", "session_step", "doc_id", "click_prob", "reward"]
    assert len(df) == 4 * 2 * 3
    assert df["click_prob"].between(0, 1).all()
    assert set(df["reward"].unique()) <= {0.0, 1.0}
    # deterministic with same seed
    df2 = sim.simulate(num_users=4, num_docs=20, num_episodes=2, slate_size=3, seed=7)
    assert df.equals(df2)
