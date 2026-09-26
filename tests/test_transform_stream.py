"""Transform streams NDJSON in chunks (no full-file frame held)."""
import json
import sys
import tracemalloc

sys.path.insert(0, ".")
from pipelines.ingest_strategy import NDJSONChunkStrategy


def test_ndjson_iter_batches_peak_memory(tmp_path):
    p = tmp_path / "big.ndjson"
    with open(p, "w") as f:
        for i in range(20_000):
            f.write(json.dumps({"mal_id": i, "title": f"A{i}"}) + "\n")
    tracemalloc.start()
    n = 0
    for df in NDJSONChunkStrategy(chunksize=2000).iter_batches(p):
        assert len(df) <= 2000
        n += len(df)
        del df  # ponytail: release each batch before next
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert n == 20_000
    assert peak < 100 * 1024 * 1024, f"peak {peak / 1e6:.1f}MB too high for chunked read"
