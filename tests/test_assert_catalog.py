"""Catalog quality gate: pure evaluate() logic (no DB needed)."""
import sys

sys.path.insert(0, ".")

from scripts.assert_catalog import THRESHOLDS, evaluate


def test_pass_on_healthy_stats():
    assert evaluate(5132, {"title": 0, "image_url": 0, "score": 239,
                           "year": 68}) == []


def test_fail_on_empty_table():
    assert evaluate(0, {}) == ["row_count is 0"]


def test_fail_messages_name_column_and_rate():
    fails = evaluate(1000, {"title": 0, "image_url": 60, "score": 50, "year": 10})
    assert any("image_url" in f and "0.060" in f for f in fails)
    assert not any("title" in f for f in fails)
    assert set(THRESHOLDS) == {"title", "image_url", "score", "year"}
