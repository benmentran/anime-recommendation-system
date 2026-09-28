"""Pure helpers for RAG retrieval: language detect, genre prefilter, rerank.

Stdlib only (no heavy deps). Shared by `rag_router.ask` and `scripts/wsl_rag_ask.py`.
"""
import re

_VI_DIACRITICS = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡ"
    r"ùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)
_VI_WORDS = frozenset(
    ["của", "những", "và", "với", "cho", "từ", "này", "kia", "gì", "nào", "không", "có", "là", "một", "người", "phim", "hay", "nhất", "giới", "thiệu", "gợi", "ý", "xem", "tôi", "muốn", "tìm", "kiếm", "kinh", "dị", "hài", "hước", "lãng", "mạn", "chiến", "đấu"]
    # Biến thể không dấu (chat thật hay gõ không dấu).
    # Cố tình BỎ: the/an/hai/cam/dong/tinh/ky/ao/bi/y — trùng từ tiếng Anh thường gặp.
    + ["cua", "nhung", "va", "voi", "cho", "tu", "nay", "kia", "gi", "nao", "khong", "co", "la", "mot", "nguoi", "phim", "nhat", "goi", "xem", "toi", "muon", "tim", "kiem", "kinh", "di", "huoc", "lang", "man", "chien", "dau", "vua", "thao"]
)

# genre -> lowercase keywords matched against the query (first match wins)
GENRE_KEYWORDS: dict[str, list[str]] = {
    "Mecha": ["mecha", "robot", "gundam", "evangelion", "votoms"],
    "Isekai": ["isekai", "reincarnat", "transferred to another world", "chuyển sinh", "dị giới"],
    "Romance": ["romance", "love story", "lãng mạn", "tình cảm"],
    "Horror": ["horror", "scary", "kinh dị"],
    "Comedy": ["comedy", "funny", "hài hước", "hài"],
    "Sports": ["sports", "football", "basketball", "thể thao", "bóng đá"],
    "Mystery": ["mystery", "detective", "trinh thám", "bí ẩn"],
    "Fantasy": ["fantasy", "magic", "phép thuật", "giả tưởng"],
    "Sci-Fi": ["sci-fi", "scifi", "science fiction", "viễn tưởng", "không gian"],
    "Slice of Life": ["slice of life", "đời thường"],
    "Action": ["action", "hành động", "chiến đấu"],
    "Drama": ["drama", "chính kịch", "tâm lý"],
}


def detect_language(query: str) -> str:
    """'vi' if Vietnamese diacritics or VN stopwords present, else 'en'. Heuristic, no deps."""
    q = query.lower()
    if _VI_DIACRITICS.search(query):
        return "vi"
    words = set(re.findall(r"[a-zà-ỹđ]+", q))
    if words & _VI_WORDS:
        return "vi"
    return "en"


def infer_genre_filter(query: str) -> str | None:
    """Genre string for Qdrant prefilter, or None when no keyword matches (pure-vector fallback)."""
    q = query.lower()
    for genre, keywords in GENRE_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return genre
    return None


def build_qdrant_filter(genre: str | None) -> dict | None:
    """Qdrant `filter` for genre prefilter; None keeps pure-vector search.

    Uses full-text `match.text` because payload `genres` is one comma-joined
    string (not an array). Returns 400 if no full-text index exists — callers
    MUST retry without filter (fallback).
    """
    if not genre:
        return None
    return {"must": [{"key": "genres", "match": {"text": genre}}]}


def rerank_hits(hits: list[dict], boost: float = 0.02) -> list[dict]:
    """Stable rerank: vector score + boost * (payload score / 10).

    Keeps semantic order; payload score only breaks near-ties.
    # ponytail: linear blend; replace with cross-encoder when quality demands it
    """
    def _key(h: dict) -> float:
        vec = h.get("score") or 0.0
        payload_score = (h.get("payload") or {}).get("score") or 0.0
        return vec + boost * (payload_score / 10.0)
    return sorted(hits, key=_key, reverse=True)
