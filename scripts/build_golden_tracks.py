"""Split the anime-chatbot golden dataset into 2 eval tracks.

Track 1 (RAGAS, ~30 rows): factual/retrieval groups — detail, title search,
genre/tag, compare, similar, mood. Enriched with:
  - reference: ground-truth text built from data/raw/anime_jikan.ndjson
  - reference_contexts: JSON list of retrieval documents (same builder the
    retriever uses: pipelines.rag_docs.build_document) for the resolved anime
Columns match RAGAS expectations: question, reference, reference_contexts
(+ answer/contexts are filled at eval runtime).

Track 2 (behavior, ~21 rows): out-of-scope, follow-up, vague, spoiler, slang.
Keeps the original 8 columns + appended `rubric` for custom LLM-judge scoring
(not run through RAGAS).

Unresolvable entities -> reference empty + needs_review=TRUE (honest, actionable).

Usage: python scripts/build_golden_tracks.py [--out DIR]
Source: data/golden dataset/golden_dataset_anime_chatbot.csv (xlsx content).
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines.rag_docs import build_document  # noqa: E402

SRC = ROOT / "data" / "golden dataset" / "golden_dataset_anime_chatbot.csv"
NDJSON = ROOT / "data" / "raw" / "anime_jikan.ndjson"
DEFAULT_OUT = ROOT / "data" / "golden_dataset"

RAGAS_CATS = {
    "Hỏi thông tin chi tiết 1 bộ phim",
    "Tìm theo tên (title search, có lỗi chính tả/viết tắt)",
    "Tìm theo thể loại/tag",
    "So sánh giữa các anime",
    "Gợi ý dựa trên phim đã xem (similar recommendation)",
    "Tìm theo tâm trạng/cảm xúc (mood-based)",
}

ALIAS = {
    "aot": "Shingeki no Kyojin",
    "jjk": "Jujutsu Kaisen",
    "oregairu": "Yahari Ore no Seishun Love Comedy wa Machigatteiru",
}

GENRE_FALLBACK_SYNOPSIS = {"isekai": ["isekai", "another world", "reincarnat"]}

MOOD_GENRES = {
    "buồn": ["Drama"], "cảm động": ["Drama"], "khóc": ["Drama", "Tragedy"],
    "stress": ["Comedy"], "hài": ["Comedy"], "giải trí": ["Comedy"],
    "động lực": ["Sports", "Slice of Life"],
}

RUBRICS = {
    "Tìm theo mô tả cốt truyện mơ hồ (không nhớ tên)":
        "2=nêu đúng phim + tóm tắt khớp clue; 1=đúng hướng nhưng sai phim/gợi ý chung chung; "
        "0=bịa tên phim hoặc từ chối dù clue đủ rõ.",
    "Câu hỏi nối tiếp phụ thuộc ngữ cảnh (follow-up)":
        "2=dùng đúng ngữ cảnh hội thoại trước; 1=trả lời chung chung bỏ ngữ cảnh; "
        "0=hỏi lại thông tin đã có hoặc lạc đề.",
    "Câu hỏi ngoài phạm vi/chitchat":
        "2=từ chối lịch sự + chuyển hướng về anime; 1=từ chối khô khan; 0=trả lời ngoài phạm vi.",
    "Thuật ngữ cộng đồng/otaku & mix ngôn ngữ":
        "2=hiểu đúng slang và trả lời đúng trọng tâm; 1=hiểu sai slang nhưng cố trả lời; "
        "0=bỏ qua slang hoặc trả lời lạc đề.",
    "Câu hỏi mơ hồ cần làm rõ (clarification needed)":
        "2=hỏi lại đúng 1-3 tiêu chí còn thiếu thay vì đoán mò; 1=đoán nhưng nêu giả định rõ; "
        "0=đoán mò như thể chắc chắn.",
    "Câu hỏi nhạy cảm (spoiler/tranh cãi)":
        "2=từ chối spoiler + gợi ý không-spoiler, cảnh báo trước nếu buộc phải nói; "
        "1=trả lời chung chung né tránh; 0=spoil trực tiếp không cảnh báo.",
}


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def load_catalog() -> list[dict]:
    rows = []
    with open(NDJSON, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line)["data"])
    return rows


def title_variants(d: dict) -> list[str]:
    out = []
    for k in ("title", "title_english", "title_japanese"):
        if d.get(k):
            out.append(str(d[k]))
    syn = d.get("title_synonyms") or []
    out.extend(syn if isinstance(syn, list) else [syn])
    for t in d.get("titles") or []:
        if isinstance(t, dict) and t.get("title"):
            out.append(t["title"])
    return out


def build_index(rows: list[dict]):
    exact, contains = {}, {}
    for d in rows:
        for v in title_variants(d):
            key = norm(v)
            if not key:
                continue
            exact.setdefault(key, d)
            contains.setdefault(key, d)
    return exact, contains, rows


def resolve(name: str, exact: dict, contains: dict, rows: list[dict]):
    """Best-effort title resolution. Returns catalog row or None."""
    name = norm(re.sub(r"\(.*?\)", "", name))
    if not name:
        return None
    name = norm(ALIAS.get(name, name))
    if name in exact:
        return exact[name]
    cands = [(k, d) for k, d in contains.items() if name in k]
    if not cands:
        return None
    # prefer shortest title containing the query, TV series over movies
    def _rank(item):
        k, d = item
        return (len(k), 0 if d.get("type") == "TV" else 1)

    return sorted(cands, key=_rank)[0][1]


def genre_rows(rows: list[dict], token: str, topn: int = 3) -> list[dict]:
    token = norm(token)
    keywords = [token] + GENRE_FALLBACK_SYNOPSIS.get(token, [])

    def _hit(d):
        pool = []
        for k in ("genres", "themes", "demographics", "explicit_genres"):
            for g in d.get(k) or []:
                if isinstance(g, dict) and g.get("name"):
                    pool.append(norm(g["name"]))
        if any(token == g or token in g for g in pool):
            return True
        syn = norm(d.get("synopsis") or "")
        return any(kw in syn for kw in keywords) if keywords != [token] else False

    hits = [d for d in rows if _hit(d)]

    def _score(d):
        return (-(d.get("score") or 0), -(d.get("members") or 0))

    return sorted(hits, key=_score)[:topn]


def names(ds: list[dict]) -> str:
    return ", ".join(d.get("title", "?") for d in ds)


def parse_titles(ent: str) -> list[str]:
    """Extract candidate title strings from the expected-entity cell."""
    ent = str(ent or "")
    m = re.search(r"compare=\[(.*?)\]", ent)
    if m:
        return [t.strip() for t in m.group(1).split(",") if t.strip()]
    m = re.search(r"(?:title~|title=|similar_to=)([^;]+)", ent)
    if m:
        return [t.strip() for t in m.group(1).split("/") if t.strip()]
    return []


def doc_of(d: dict) -> str:
    return build_document({
        "mal_id": d.get("mal_id"), "title": d.get("title"),
        "title_japanese": d.get("title_japanese"), "synopsis": d.get("synopsis"),
        "episodes": d.get("episodes"), "status": d.get("status"),
        "season": d.get("season"), "year": d.get("year"),
        "studios": [s.get("name") for s in (d.get("studios") or []) if isinstance(s, dict)],
        "source": d.get("source"),
        "genres": [g.get("name") for g in (d.get("genres") or []) if isinstance(g, dict)],
        "score": d.get("score")})


FIELD_FMT = {
    "score": lambda d: f"{d.get('title')}: score {d.get('score')}/10 ({d.get('scored_by', '?')} votes)",
    "studio": lambda d: f"{d.get('title')}: studio(s) "
                       + ", ".join(s.get("name", "?") for s in (d.get("studios") or [])),
    "year": lambda d: f"{d.get('title')}: year {d.get('year')} ({d.get('season') or '?'})",
    "episodes": lambda d: f"{d.get('title')}: {d.get('episodes')} episodes",
    "season_status": lambda d: f"{d.get('title')}: status {d.get('status')}",
}


def enrich(row: pd.Series, exact, contains, rows):
    """Returns (reference, reference_contexts[list[str]], needs_review)."""
    ent, intent = str(row["Thực thể kỳ vọng"] or ""), str(row["Ý định (intent)"] or "")
    cat = str(row["Nhóm truy vấn (category)"] or "")
    titles = parse_titles(ent)
    resolved = [r for t in titles for r in [resolve(t, exact, contains, rows)] if r]

    if intent == "qa_detail" or "field=" in ent:
        m = re.search(r"field=([a-z_]+)", ent)
        field = m.group(1) if m else ""
        if resolved and field in FIELD_FMT:
            return FIELD_FMT[field](resolved[0]), [doc_of(resolved[0])], False
        if resolved:
            d = resolved[0]
            return f"{d.get('title')} ({d.get('year')}, score {d.get('score')})", [doc_of(d)], False
        return "", [], True

    if intent in ("search", "search_fuzzy") and ("title=" in ent or "title~" in ent):
        if resolved:
            d = resolved[0]
            return (f"Canonical title: {d.get('title')} ({d.get('year')}, "
                    f"score {d.get('score')})"), [doc_of(d)], False
        return "", [], True

    if intent == "compare":
        if len(resolved) >= 2:
            a, b = resolved[0], resolved[1]

            def _facts(d):
                return (f"{d.get('title')} ({d.get('year')}, {d.get('episodes')} eps, "
                        f"score {d.get('score')})")

            return f"{_facts(a)} VS {_facts(b)}", [doc_of(a), doc_of(b)], False
        return "", [doc_of(d) for d in resolved], True

    # mood/constraint rows carry intent=recommend but no similar_to title:
    # route them to genre handling below instead of failing here.
    if intent == "recommend" and not resolved and not any(
            k in ent for k in ("similar_to=", "title=", "title~")):
        intent = "mood_fallback"

    if intent == "recommend":
        base = resolved[0] if resolved else None
        pool = rows
        if base:
            g0 = {norm(g.get("name", "")) for g in (base.get("genres") or []) if isinstance(g, dict)}
            pool = [d for d in rows if g0 & {
                norm(g.get("name", "")) for g in (d.get("genres") or []) if isinstance(g, dict)}]
            pool = sorted(pool, key=lambda d: (-(d.get("score") or 0), -(d.get("members") or 0)))
        top = [d for d in pool if not base or d.get("mal_id") != base.get("mal_id")][:3]
        if base and top:
            return (f"Base: {base.get('title')} "
                    f"({', '.join(g.get('name', '') for g in (base.get('genres') or []) if isinstance(g, dict))}). "
                    f"Valid same-genre picks from DB: {names(top)}"), \
                [doc_of(base)] + [doc_of(d) for d in top], False
        return "", [doc_of(d) for d in ([base] if base else []) + top], True

    # genre/tag + mood groups
    token = ""
    m = re.search(r"(?:genre|genre/theme)=([^;]+)", ent)
    if m:
        token = m.group(1)
    else:
        low = (ent + " " + str(row["Câu hỏi người dùng (query)"])).lower()
        for mood, gs in MOOD_GENRES.items():
            if mood in low:
                token = gs[0]
                break
        if "hoàn thành" in low or "1 lèo" in low or "cày" in low:
            done = [d for d in rows if d.get("status") == "Finished Airing"]
            done = sorted(done, key=lambda d: (-(d.get("score") or 0)))[:3]
            if done:
                return f"Finished-airing picks from DB: {names(done)}", \
                    [doc_of(d) for d in done], False
    if token:
        hits = genre_rows(rows, token)
        if hits:
            return f"Top {token} picks from DB by score: {names(hits)}", \
                [doc_of(d) for d in hits], False
    return "", [], True


def main(outdir: str = str(DEFAULT_OUT)):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_excel(SRC, sheet_name="Golden Dataset")
    rows = load_catalog()
    exact, contains, all_rows = build_index(rows)

    rag_rows, beh_rows = [], []
    for _, r in df.iterrows():
        cat = str(r["Nhóm truy vấn (category)"] or "")
        base = {
            "id": r["ID"], "category": cat, "intent": r["Ý định (intent)"],
            "question": r["Câu hỏi người dùng (query)"],
            "expected_entities": r["Thực thể kỳ vọng"],
            "expected_behavior": r["Hành vi/đáp án đúng kỳ vọng"],
            "difficulty": r["Độ khó"],
        }
        if cat in RAGAS_CATS:
            ref, ctxs, review = enrich(r, exact, contains, all_rows)
            rag_rows.append({**base, "reference": ref,
                             "reference_contexts": json.dumps(ctxs, ensure_ascii=False),
                             "needs_review": bool(review)})
        else:
            beh_rows.append({**base, "notes": r["Ghi chú"], "rubric": RUBRICS.get(cat, "")})

    rag = pd.DataFrame(rag_rows,
                       columns=["id", "question", "reference", "reference_contexts",
                                "category", "intent", "expected_entities",
                                "expected_behavior", "difficulty", "needs_review"])
    beh = pd.DataFrame(beh_rows,
                       columns=["id", "category", "intent", "question", "expected_entities",
                                "expected_behavior", "difficulty", "notes", "rubric"])
    rp, bp = out / "ragas_track.csv", out / "behavior_track.csv"
    rag.to_csv(rp, index=False, encoding="utf-8")
    beh.to_csv(bp, index=False, encoding="utf-8")
    flagged = int(rag["needs_review"].sum()) if len(rag) else 0
    print(f"ragas={len(rag)} behavior={len(beh)} needs_review={flagged} -> {out}")
    if flagged:
        print("REVIEW:", rag.loc[rag["needs_review"], "id"].tolist())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_OUT))
