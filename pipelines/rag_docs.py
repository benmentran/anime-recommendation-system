"""Build the retrieval Document for one anime catalog row (pure, stdlib only)."""

SYNOPSIS_MAX = 1500


def _names(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []


def build_document(row: dict) -> str:
    """One text block per anime: title, facets, synopsis. Empty parts dropped."""
    title = row.get("title") or f"Anime {row.get('mal_id')}"
    lines = [f"Title: {title}"]
    if row.get("title_japanese") and row["title_japanese"] != title:
        lines.append(f"Japanese title: {row['title_japanese']}")
    facets = []
    if row.get("year"):
        facets.append(f"Year: {row['year']}")
    if row.get("season"):
        facets.append(f"Season: {row['season']}")
    if row.get("episodes"):
        facets.append(f"Episodes: {row['episodes']}")
    if row.get("status"):
        facets.append(f"Status: {row['status']}")
    if row.get("source"):
        facets.append(f"Source: {row['source']}")
    studios = _names(row.get("studios"))
    if studios:
        facets.append(f"Studios: {', '.join(studios)}")
    genres = _names(row.get("genres"))
    if genres:
        facets.append(f"Genres: {', '.join(genres)}")
    if row.get("score"):
        facets.append(f"Score: {row['score']}/10")
    if facets:
        lines.append(" | ".join(facets))
    synopsis = (row.get("synopsis") or "").strip()
    if synopsis:
        lines.append(f"Synopsis: {synopsis[:SYNOPSIS_MAX]}")
    return "\n".join(lines)
