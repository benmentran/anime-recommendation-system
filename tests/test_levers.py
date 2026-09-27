"""Workstream 8 levers: translate prompt + skip-EN, loose genre-map, cross-encoder wrapper.

All mocked/pure — no API calls, no model download.
"""
import asyncio
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

from pipelines.rerank import doc_text, rerank_cross_encoder  # noqa: E402
from pipelines.translate_query import clear_cache, translate_query  # noqa: E402
from scripts.score_loose import is_loose_hit, loose_metrics  # noqa: E402


def _oai(reply="translated query"):
    """Mock AsyncOpenAI capturing chat.completions.create kwargs."""
    seen = {}

    async def _create(**kw):
        seen.update(kw)
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=reply))])

    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))), seen


def test_translate_prompt_preserves_titles_and_replies_only_translation():
    clear_cache()
    oai, seen = _oai("scary school horror anime")
    out = asyncio.run(translate_query("kinh dị học đường có ma", oai))
    assert out == "scary school horror anime"
    sys_prompt = seen["messages"][0]["content"]
    assert "English" in sys_prompt
    assert "titles" in sys_prompt.lower()  # anime titles/names stay untranslated
    assert "ONLY" in sys_prompt  # reply with only the translation


def test_translate_skips_english_without_api_call():
    clear_cache()
    calls = {"n": 0}

    async def _create(**kw):
        calls["n"] += 1
        raise AssertionError("must not be called for EN input")

    oai = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    q = "political mecha anime like Gundam"
    assert asyncio.run(translate_query(q, oai)) == q
    assert calls["n"] == 0


def test_loose_genre_map_pure_fixture():
    id_genres = {11: {"action", "drama"}, 12: {"comedy"}, 13: {"drama"}}
    assert is_loose_hit(11, {"drama"}, id_genres)
    assert is_loose_hit(13, {"action", "drama"}, id_genres)
    assert not is_loose_hit(12, {"drama"}, id_genres)
    m = loose_metrics([11, 12, 13], {"drama"}, id_genres, 2)
    assert m["mrr"] == 1.0
    assert m["p5"] == 0.4


class _MockCE:
    def __init__(self, scores):
        self._scores = scores

    def predict(self, pairs, *args, **kwargs):
        assert len(pairs) == len(self._scores)
        return self._scores


def test_cross_encoder_wrapper_orders_and_cuts_top5():
    hits = [{"payload": {"mal_id": i, "title": f"T{i}",
                         "genres": "Action", "synopsis": "s"}} for i in range(7)]
    scores = [0.1, 0.9, 0.3, 0.8, 0.2, 0.7, 0.4]
    out = rerank_cross_encoder("q", hits, doc_text, model=_MockCE(scores), top_k=5)
    assert [h["payload"]["mal_id"] for h in out] == [1, 3, 5, 6, 2]
