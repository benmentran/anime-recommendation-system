"""Cross-encoder rerank for retrieval (Workstream 8 V3).

Lazy-loads ms-marco-MiniLM via sentence-transformers. Missing lib/model ->
return hits unchanged + warning, NEVER crash the benchmark.
Memory-safe: single torch thread, no tokenizer fork pool, truncated docs,
small predict batches (a previous full run OOMed a 16GB box).
# ponytail: MiniLM default; swap model name when quality demands it
"""

import os
from collections.abc import Callable

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DOC_MAX_CHARS = 1000  # cross-encoder truncates at 512 tokens anyway
PREDICT_BATCH = 4

_model = None


def _load_model(model_name: str = MODEL_NAME):
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        try:
            import torch

            torch.set_num_threads(1)
            torch.set_num_interop_threads(1)
        except Exception:  # noqa: BLE001 - thread cap is best-effort
            pass
        _model = CrossEncoder(model_name, device="cpu")
    return _model


def release_model() -> None:
    """Free torch weights after a benchmark run. Call once at the end."""
    global _model
    _model = None
    try:
        import gc

        gc.collect()
    except Exception:  # noqa: BLE001
        pass


def rerank_cross_encoder(
    query: str,
    hits: list[dict],
    get_text: Callable[[dict], str],
    model=None,
    top_k: int = 10,
    batch_size: int = PREDICT_BATCH,
) -> list[dict]:
    """Score (query, doc-text) pairs, return top_k. Fallback: input order."""
    if not hits:
        return hits
    try:
        enc = model if model is not None else _load_model()
        pairs = [(query, get_text(h)[:DOC_MAX_CHARS]) for h in hits]
        scores = enc.predict(pairs, batch_size=batch_size, show_progress_bar=False)
        ordered = sorted(zip(hits, scores), key=lambda p: float(p[1]), reverse=True)
        return [h for h, _ in ordered[:top_k]]
    except Exception as e:  # noqa: BLE001 - fallback path is the point
        print(f"cross-encoder unavailable ({e}), skipping rerank", flush=True)
        return hits[:top_k]


def doc_text(hit: dict) -> str:
    """Rerank text from Qdrant payload (title + genres + synopsis)."""
    p = hit.get("payload") or {}
    return f"{p.get('title') or ''} {p.get('genres') or ''} {p.get('synopsis') or ''}".strip()
