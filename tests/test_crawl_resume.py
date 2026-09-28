"""Crawl resume: second run must not re-call API for checkpointed IDs."""
import asyncio
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, ".")
from pipelines import collection as pipe


def test_resume_skips_checkpointed(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, "DATA_DIR", tmp_path)
    monkeypatch.setattr(pipe, "OUT", tmp_path / "anime_jikan.ndjson")
    monkeypatch.setattr(pipe, "CHECKPOINT", tmp_path / "crawled_ids.txt")
    (tmp_path / "crawled_ids.txt").write_text("1\n2\n")

    async def fake_pool(*a, **k):
        raise ConnectionError("no db in test")

    async def run():
        with patch.object(pipe, "asyncpg") as mock_pg, \
             patch("pipelines.collection.JikanClient") as MC:
            mock_pg.connect.side_effect = fake_pool
            inst = MC.return_value
            inst.get_anime_full = AsyncMock(return_value=({}, __import__("datetime").datetime.now()))
            inst.close = AsyncMock()
            await pipe.crawl([1, 2, 3])
            return inst.get_anime_full.await_count

    assert asyncio.run(run()) == 1  # only id 3 fetched
