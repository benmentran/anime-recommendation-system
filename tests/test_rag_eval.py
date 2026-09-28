"""RAG eval set: fixed EN/VI queries with expectations (Workstream 4 follow-up).

Unit cases below run on mocked retrieval (no infra). Cases needing the live
Qdrant `anime` index + OpenAI calls are marked `needs_live_index` and skipped
by default — run them by hand via `scripts/wsl_rag_ask.py "<query>"`.
"""
import sys

import pytest

sys.path.insert(0, ".")

from pipelines.rag_prompt import build_messages
from pipelines.rag_retrieval import (
    build_qdrant_filter,
    detect_language,
    infer_genre_filter,
    rerank_hits,
)

# query, expected lang, expected genre filter, titles expected in live top-5
EVAL_CASES = [
    ("modern political mecha with a villain protagonist like Gundam Iron-Blooded Orphans",
     "en", "Mecha", ["Mobile Suit Gundam: Iron-Blooded Orphans", "86"]),
    ("mecha anime about war and politics with child soldiers",
     "en", "Mecha", ["Mobile Suit Gundam: Iron-Blooded Orphans", "86"]),
    ("romantic comedy anime set in high school",
     "en", "Comedy", []),
    ("kinh dị học đường Nhật Bản có ma quỷ",
     "vi", "Horror", []),
    ("gợi ý anime tình cảm lãng mạn nhẹ nhàng để xem cuối tuần",
     "vi", "Romance", []),
    ("isekai where the main character is overpowered from the start",
     "en", "Isekai", []),
    ("anime bóng đá thể thao truyền cảm hứng",
     "vi", "Sports", []),
]

needs_live_index = pytest.mark.skip(reason="needs live Qdrant index + OPENAI_API_KEY")


def _titles(cases):
    return [c[0] for c in cases]


@pytest.mark.parametrize("query,lang,genre,_", EVAL_CASES)
def test_eval_language_detected(query, lang, genre, _):
    assert detect_language(query) == lang


@pytest.mark.parametrize("query", [
    "goi y anime vua hanh dong vua tinh cam",
    "tim anime hai huoc de xem cuoi tuan",
    "anime nao hay nhat nam nay",
    "muon xem phim kinh di khong qua so",
])
def test_detect_unaccented_vietnamese(query):
    # Chat thật hay gõ không dấu; trước đây rớt về "en" (bivector search nhầm vector).
    assert detect_language(query) == "vi"


@pytest.mark.parametrize("query", [
    "isekai where the main character is overpowered from the start",
    "romantic comedy anime set in high school",
    "the best action anime with a strong story",
])
def test_detect_english_not_confused(query):
    assert detect_language(query) == "en"


@pytest.mark.parametrize("query,_lang,genre,_", EVAL_CASES)
def test_eval_genre_filter(query, _lang, genre, _):
    assert infer_genre_filter(query) == genre


def test_genre_filter_none_means_pure_vector_fallback():
    assert build_qdrant_filter(None) is None
    f = build_qdrant_filter("Mecha")
    assert f == {"must": [{"key": "genres", "match": {"text": "Mecha"}}]}


def test_mock_retrieval_top5_contains_expected():
    # unit: mocked Qdrant hits for the mecha-politics query keep Gundam IBO/86 in top-5
    hits = [
        {"score": 0.80, "payload": {"mal_id": 1, "title": "Cowboy Bebop", "score": 8.75}},
        {"score": 0.78, "payload": {"mal_id": 2, "title": "86", "score": 8.30}},
        {"score": 0.77, "payload": {"mal_id": 3, "title": "Armored Trooper Votoms", "score": 7.80}},
        {"score": 0.76, "payload": {"mal_id": 4, "title": "Mobile Suit Gundam: Iron-Blooded Orphans", "score": 8.10}},
        {"score": 0.75, "payload": {"mal_id": 5, "title": "Nadesico", "score": 7.40}},
        {"score": 0.74, "payload": {"mal_id": 6, "title": "Giant Robo", "score": 7.60}},
    ]
    top5 = [h["payload"]["title"] for h in rerank_hits(hits)[:5]]
    assert "86" in top5
    assert "Mobile Suit Gundam: Iron-Blooded Orphans" in top5


def test_rerank_prefers_higher_payload_score_on_near_tie():
    hits = [
        {"score": 0.800, "payload": {"mal_id": 1, "title": "Low", "score": 5.0}},
        {"score": 0.799, "payload": {"mal_id": 2, "title": "High", "score": 9.5}},
    ]
    assert rerank_hits(hits)[0]["payload"]["title"] == "High"
    # clear vector winner stays on top (semantic order preserved)
    hits[0]["score"] = 0.95
    assert rerank_hits(hits)[0]["payload"]["title"] == "Low"


@pytest.mark.parametrize("query,lang,_,__", EVAL_CASES)
def test_eval_answer_language_pinned(query, lang, _, __):
    msgs = build_messages(query, [])
    if lang == "vi":
        assert "ONLY in Vietnamese" in msgs[0]["content"]
    else:
        assert "ONLY in English" in msgs[0]["content"]


@needs_live_index
def test_live_mecha_politics_top5():
    """LIVE: wsl_rag_ask.py '<mecha query>' must return Gundam IBO or 86 in top-5."""
    pytest.fail("LIVE-only: needs live Qdrant index + OPENAI_API_KEY; run via scripts/wsl_rag_ask.py")


@needs_live_index
def test_live_vietnamese_query_answers_vietnamese():
    """LIVE: VI query must be answered in Vietnamese (no Spanish/English drift)."""
    pytest.fail("LIVE-only: needs live Qdrant index + OPENAI_API_KEY; run via scripts/wsl_rag_ask.py")
