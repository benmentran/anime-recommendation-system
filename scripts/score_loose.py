"""V2: loose-relevance rescore from saved benchmark rows (0 cost, no infra).

Loose definition: a retrieved anime counts as relevant if it shares >= 1
genre with the golden relevant set of that row. Reported ALONGSIDE strict
numbers (never replaces them); winner selection stays strict NDCG@5.

Usage: python scripts/score_loose.py [benchmark_hybrid.json]
"""
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_golden_tracks import (build_index, genre_rows, load_catalog,
                                         MOOD_GENRES, parse_titles, resolve)


def genre_pool(d: dict) -> set[str]:
    """Lowercased genre/theme/demographic names of one catalog row."""
    out = set()
    for k in ("genres", "themes", "demographics", "explicit_genres"):
        for g in d.get(k) or []:
            if isinstance(g, dict) and g.get("name"):
                out.add(g["name"].strip().lower())
    return out


def genres_of(d: dict) -> set[str]:
    return genre_pool(d)


def is_loose_hit(mid: int, golden_genres: set[str], id_genres: dict[int, set[str]]) -> bool:
    """A retrieved id counts iff it shares >= 1 genre with the golden set."""
    return bool(golden_genres) and bool(id_genres.get(mid, set()) & golden_genres)


def loose_metrics(ranked: list[int], golden_genres: set[str],
                  id_genres: dict[int, set[str]], n_golden: int = 0) -> dict:
    """P@5 / NDCG@5 / MRR over a ranked id list under loose relevance.

    n_golden is informational only (count of golden items defining the pool);
    ranking metrics always use the provided list with fixed @5 denominator.
    """
    rel = {m for m in ranked if is_loose_hit(m, golden_genres, id_genres)}
    _ = n_golden
    return {"p5": p_at_k(ranked, rel, 5),
            "ndcg5": ndcg_at_k(ranked, rel, 5),
            "mrr": mrr(ranked, rel)}


def golden_genres(row, exact, contains, rows) -> set[str]:
    """Union of genres over the golden relevant set (same resolvers as builder)."""
    ent, intent = row["expected_entities"], row["intent"]
    titles = parse_titles(ent)
    resolved = [r for t in titles for r in [resolve(t, exact, contains, rows)] if r]
    if resolved and (intent in ("qa_detail", "search", "search_fuzzy", "compare",
                                "recommend") or "field=" in ent or "title=" in ent
                     or "title~" in ent or "similar_to=" in ent or "compare=" in ent):
        return {g for d in resolved for g in genres_of(d)}
    token = ""
    m = __import__("re").search(r"(?:genre|genre/theme)=([^;]+)", ent)
    if m:
        token = m.group(1)
    else:
        low = (ent + " " + row["question"]).lower()
        for mood, gs in MOOD_GENRES.items():
            if mood in low:
                token = gs[0]
                break
    hits = genre_rows(rows, token) if token else []
    return {g for d in hits for g in genres_of(d)}


def p_at_k(ranked, rel, k):
    return len([i for i in ranked[:k] if i in rel]) / k if rel else 0.0


def ndcg_at_k(ranked, rel, k):
    dcg = sum(1.0 / math.log2(i + 2) for i, m in enumerate(ranked[:k]) if m in rel)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel), k)))
    return dcg / ideal if ideal else 0.0


def mrr(ranked, rel):
    for i, m in enumerate(ranked):
        if m in rel:
            return 1.0 / (i + 1)
    return 0.0


def main(path: str):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    with open(ROOT / "data/golden_dataset/ragas_track.csv", encoding="utf-8") as f:
        gold = {g["id"]: g for g in csv.DictReader(f)}
    rows = load_catalog()
    exact, contains, all_rows = build_index(rows)
    by_id = {d["mal_id"]: d for d in rows}
    agg = {"p5": [], "n5": [], "mrr": []}
    for r in data["rows"]:
        g = gold[str(r["id"])]
        gg = golden_genres(g, exact, contains, all_rows)
        rel = {mid for mid in r["ranked"][:10]
               if gg and (genres_of(by_id.get(mid, {})) & gg)}
        agg["p5"].append(p_at_k(r["ranked"], rel, 5))
        agg["n5"].append(ndcg_at_k(r["ranked"], rel, 5))
        agg["mrr"].append(mrr(r["ranked"], rel))
    out = {k: round(sum(v) / len(v), 4) for k, v in agg.items()}
    print("LOOSE:", json.dumps(out, ensure_ascii=False), flush=True)
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         str(ROOT / "data/golden_dataset/benchmark_hybrid.json"))
