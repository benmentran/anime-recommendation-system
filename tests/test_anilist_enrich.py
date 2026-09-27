"""AniList enrichment pure units: html strip + media->row mapping (no network/DB)."""
import sys

sys.path.insert(0, ".")

from pipelines.anilist_enrich import strip_html, to_row


def test_strip_html_truncates_and_cleans():
    assert strip_html("<br>Hi <i>there</i>  x", limit=20) == "Hi there x"
    assert strip_html(None) is None
    assert strip_html("") is None


def test_to_row_maps_scores_and_tags():
    m = {"idMal": 1, "tags": [{"name": "Isekai", "rank": 95, "isMediaSpoiler": False}],
         "averageScore": 85, "popularity": 1000, "favourites": 50,
         "description": "A <br> tale"}
    r = to_row(m)
    assert r["mal_id"] == 1
    assert r["tags_anilist"] == [{"name": "Isekai", "weight": 95}]
    assert r["score_anilist"] == 8.5
    assert r["description_anilist"] == "A tale"


def test_to_row_skips_missing_mal_id_and_null_score():
    assert to_row({"tags": []}) is None
    r = to_row({"idMal": 2, "averageScore": None})
    assert r["score_anilist"] is None and r["tags_anilist"] == []
