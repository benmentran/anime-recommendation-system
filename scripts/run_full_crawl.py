"""Full anime crawl: discover IDs (AniList top + seasonal) then fetch details.

Resumable: checkpoint data/raw/crawled_ids.txt + skip-fresh via Postgres.
Usage: DATABASE_URL=... python scripts/run_full_crawl.py [top_limit]
(Airflow DAG calls the same two functions.)
"""
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG_FILE = ROOT / "logs" / "crawl.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


class _Tee:
    """Mirror all stdout (incl. prints from pipelines) into the log file."""

    def __init__(self, *files):
        self.files = files

    def write(self, data):
        for f in self.files:
            f.write(data)

    def flush(self):
        for f in self.files:
            f.flush()


_logf = open(LOG_FILE, "a", encoding="utf-8")
sys.stdout = _Tee(sys.stdout, _logf)
sys.stderr = _Tee(sys.stderr, _logf)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("crawl")

from pipelines.collection import crawl
from pipelines.discovery import discover_all


async def main(top_limit: int = 5000):
    ids = await discover_all(None, top_limit)
    print(f"DISCOVERY_DONE total={len(ids)}", flush=True)
    await crawl(ids)
    print("CRAWL_DONE", flush=True)


def _single_instance():
    """Exit if another crawl is already running (stray duplicate spawns)."""
    import os

    lock = ROOT / "logs" / "crawl.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        try:
            pid = int(lock.read_text().strip())
            os.kill(pid, 0)  # alive?
            print(f"another crawl running (pid {pid}), exiting")
            return False
        except (ValueError, OSError):
            lock.write_text(str(os.getpid()))  # stale lock, take over
            return True


if __name__ == "__main__":
    if not _single_instance():
        sys.exit(0)
    try:
        limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
        asyncio.run(main(limit))
    finally:
        try:
            (ROOT / "logs" / "crawl.lock").unlink()
        except OSError:
            pass
