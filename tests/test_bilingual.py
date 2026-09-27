"""Bilingual retrieval: named-vector points, JSON-string genres, translate passthrough."""
import sys
from unittest.mock import AsyncMock

sys.path.insert(0, ".")

from pipelines.rag_docs import _names, build_document
from pipelines.rag_index import build_points


def test_names_parses_jsonb_string():
    assert _names('["Action", "Drama"]') == ["Action", "Drama"]
    assert _names(["A"]) == ["A"]
    assert _names(None) == []


def test_build_points_named_vectors():
    chunk = [{"mal_id": 1, "title": "X", "genres": ["Mecha"], "year": 2000,
              "score": 8.0, "image_url": None, "synopsis": "s"}]
    pts = build_points(chunk, [[0.1] * 4], [[0.2] * 4])
    assert pts[0]["vector"] == {"en": [0.1] * 4, "vi": [0.2] * 4}
    assert pts[0]["id"] == 1


def test_build_points_unnamed_legacy():
    chunk = [{"mal_id": 2, "title": "Y", "genres": "[]", "year": None,
              "score": None, "image_url": None, "synopsis": None}]
    pts = build_points(chunk, [[0.3] * 4])
    assert pts[0]["vector"] == [0.3] * 4


def test_build_document_keeps_genres_from_json_string():
    doc = build_document({"mal_id": 1, "title": "X", "genres": '["Mecha", "Drama"]',
                          "tags_anilist": []})
    assert "Genres: Mecha, Drama" in doc


def test_translate_query_passthrough():
    import asyncio

    from pipelines.translate_query import translate_query

    async def run():
        oai = AsyncMock()
        oai.chat.completions.create.return_value.choices = [
            type("C", (), {"message": type("M", (), {"content": " EN text "})()})()]
        out_vi = await translate_query("phim hành động hay", oai)
        out_en = await translate_query("good action anime", oai)
        return out_vi, out_en, oai.chat.completions.create.await_count

    vi, en, calls = asyncio.run(run())
    assert vi == "EN text"  # vietnamese -> translated
    assert en == "good action anime"  # english passes through, no API call
    assert calls == 1
