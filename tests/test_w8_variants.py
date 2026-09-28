"""Workstream 8 variants: translate cache/passthrough, cross-encoder rerank, loose logic."""
import asyncio
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

from pipelines.rerank import doc_text, rerank_cross_encoder
from pipelines.translate_query import clear_cache, translate_query
from scripts.score_loose import genre_pool, is_loose_hit, loose_metrics


def _oai(reply=None):
    calls = {"n": 0}

    async def _create(**kw):
        calls["n"] += 1
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=reply))])

    oai = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    return oai, calls


def test_translate_en_passthrough_no_api_call():
    clear_cache()
    oai, calls = _oai("UNUSED")
    out = asyncio.run(translate_query("modern political mecha like Gundam", oai))
    assert out == "modern political mecha like Gundam"
    assert calls["n"] == 0


def test_translate_vi_cached_after_first_call():
    clear_cache()
    oai, calls = _oai("scary school horror anime with ghosts")
    q = "kinh dị học đường Nhật Bản có ma quỷ"
    assert asyncio.run(translate_query(q, oai)) == "scary school horror anime with ghosts"
    assert asyncio.run(translate_query(q, oai)) == "scary school horror anime with ghosts"
    assert calls["n"] == 1


class _MockEnc:
    def __init__(self, scores):
        self._scores = scores

    def predict(self, pairs, *args, **kwargs):
        assert len(pairs) == len(self._scores)
        return self._scores


def test_rerank_orders_by_mock_scores():
    hits = [{"payload": {"mal_id": i, "title": t}} for i, t in enumerate(["A", "B", "C"])]
    out = rerank_cross_encoder("q", hits, lambda h: h["payload"]["title"],
                               model=_MockEnc([0.1, 0.9, 0.5]), top_k=3)
    assert [h["payload"]["title"] for h in out] == ["B", "C", "A"]


def test_rerank_fallback_keeps_order_on_error():
    class _Boom:
        def predict(self, pairs):
            raise RuntimeError("no model")

    hits = [{"payload": {"mal_id": i}} for i in range(3)]
    assert rerank_cross_encoder("q", hits, doc_text, model=_Boom(), top_k=2) == hits[:2]


def test_rerank_empty_passthrough():
    assert rerank_cross_encoder("q", [], doc_text, model=_MockEnc([])) == []


def test_loose_hit_shares_one_genre():
    idg = {1: {"action", "drama"}, 2: {"comedy"}, 3: {"drama", "romance"}}
    assert is_loose_hit(3, {"drama"}, idg)
    assert not is_loose_hit(2, {"drama"}, idg)
    assert not is_loose_hit(99, {"drama"}, idg)  # unknown id -> miss
    assert not is_loose_hit(1, set(), idg)  # empty relevant genres -> miss


def test_genre_pool_collects_all_keys():
    d = {"genres": [{"name": "Action"}], "themes": [{"name": "Mecha"}],
         "demographics": [], "explicit_genres": [{"name": "Gore"}]}
    assert genre_pool(d) == {"action", "mecha", "gore"}


def test_loose_metrics_toy():
    idg = {1: {"action"}, 2: {"comedy"}, 3: {"action", "drama"}}
    m = loose_metrics([1, 2, 3], {"action"}, idg, 2)
    assert m["p5"] == 0.4  # 2 of 5 (only 3 ranked, rest miss)
    assert m["mrr"] == 1.0
    assert 0.0 < m["ndcg5"] <= 1.0
    z = loose_metrics([1], set(), idg, 0)
    assert z == {"p5": 0.0, "ndcg5": 0.0, "mrr": 0.0}
