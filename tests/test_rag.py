"""RAG pure units: document builder + prompt construction (no network)."""
import sys

sys.path.insert(0, ".")

from pipelines.rag_docs import build_document
from pipelines.rag_prompt import SYSTEM_PROMPT, build_messages


def test_build_document_full_row():
    doc = build_document({
        "mal_id": 5114, "title": "Fullmetal Alchemist: Brotherhood",
        "title_japanese": "Hagane no Renkinjutsushi",
        "synopsis": "Two brothers seek the Philosopher's Stone.",
        "episodes": 64, "status": "Finished Airing", "season": "spring",
        "year": 2009, "studios": ["Bones"], "source": "Manga",
        "genres": ["Action", "Adventure"], "score": 9.11})
    assert "Fullmetal Alchemist: Brotherhood" in doc
    assert "Bones" in doc and "Action, Adventure" in doc
    assert "9.11" in doc and "Philosopher's Stone" in doc


def test_build_document_sparse_row():
    doc = build_document({"mal_id": 1, "title": None, "synopsis": None,
                          "studios": [], "genres": []})
    assert "Anime 1" in doc  # fallback title, no crash on Nones


def test_build_prompt_grounds_and_caps():
    cands = [{"mal_id": 1, "title": "Cowboy Bebop", "genres": "Action, Sci-Fi",
              "year": 1998, "score": 8.75, "synopsis": "Bounty hunters in space."}]
    msgs = build_messages("mecha chính trị?", cands)
    assert msgs[0]["role"] == "system" and "ONLY" in msgs[0]["content"]
    assert "Cowboy Bebop" in msgs[1]["content"]
    assert "mecha chính trị?" in msgs[1]["content"]
    assert SYSTEM_PROMPT  # non-empty guard
