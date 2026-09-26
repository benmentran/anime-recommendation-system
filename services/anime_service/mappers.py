"""Jikan + AniList -> internal catalog row (stdlib only)."""


def to_catalog(mal_id: int, jikan: dict, anilist_tags: list[dict] | None = None) -> dict:
    images = (jikan.get("images", {}).get("jpg") or {})
    return {
        "mal_id": mal_id,
        "title": jikan.get("title") or f"Anime {mal_id}",
        "title_japanese": jikan.get("title_japanese"),
        "synopsis": jikan.get("synopsis"),
        "episodes": jikan.get("episodes"),
        "status": jikan.get("status"),
        "season": jikan.get("season"),
        "year": jikan.get("year"),
        "studios": [s.get("name") for s in (jikan.get("studios") or []) if s.get("name")],
        "source": jikan.get("source"),
        "genres": [g.get("name") for g in (jikan.get("genres") or []) if g.get("name")],
        "tags": [
            {"name": t.get("name"), "weight": t.get("rank") or 0}
            for t in (anilist_tags or []) if t.get("name")
        ],
        "score": jikan.get("score"),
        "image_url": images.get("large_image_url") or images.get("image_url"),
    }
