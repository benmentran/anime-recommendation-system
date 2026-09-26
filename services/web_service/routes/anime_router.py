"""BFF anime routes: JSON only, single origin for SPA. Reads anime_catalog."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_service.db import get_session
from services.web_service.schemas.anime_schemas import AnimeDetail, AnimeMini

router = APIRouter(prefix="/api/v1/anime", tags=["anime"])


def _mini(r) -> dict:
    return {"id": r.mal_id, "title": r.title, "title_japanese": r.title_japanese,
            "image_url": r.image_url, "score": r.score, "year": r.year}


MINI_COLS = "mal_id, title, title_japanese, image_url, score, year"


@router.get("/trending", response_model=list[AnimeMini])
async def trending(limit: int = Query(20, le=50), s: AsyncSession = Depends(get_session)):
    rows = (await s.execute(text(
        f"SELECT {MINI_COLS} FROM anime_catalog "
        "ORDER BY score DESC NULLS LAST LIMIT :n"), {"n": limit})).all()
    return [_mini(r) for r in rows]


@router.get("/search", response_model=list[AnimeMini])
async def search(q: str = "", genre: str | None = None, year: int | None = None,
                 limit: int = Query(20, le=50), s: AsyncSession = Depends(get_session)):
    rows = (await s.execute(text(
        f"SELECT {MINI_COLS} FROM anime_catalog "
        "WHERE title ILIKE :q "
        "AND (:genre IS NULL OR genres ? :genre) "
        "AND (:year IS NULL OR year = :year) LIMIT :n"),
        {"q": f"%{q}%", "genre": genre, "year": year, "n": limit})).all()
    return [_mini(r) for r in rows]


@router.get("/{mal_id}", response_model=AnimeDetail)
async def detail(mal_id: int, s: AsyncSession = Depends(get_session)):
    r = (await s.execute(text("SELECT * FROM anime_catalog WHERE mal_id = :i"), {"i": mal_id})).first()
    if r is None:
        raise HTTPException(404, "anime not found")
    d = dict(r._mapping)
    return {"id": d["mal_id"], **{k: d.get(k) for k in (
        "title", "title_japanese", "synopsis", "episodes", "status", "season",
        "year", "studios", "source", "genres", "tags", "score", "image_url")}}


@router.get("/{mal_id}/recommendations", response_model=list[AnimeMini])
async def recommendations(mal_id: int, limit: int = Query(10, le=25),
                          s: AsyncSession = Depends(get_session)):
    # ponytail: genre-overlap similarity in SQL; CF hybrid plugs in later
    rows = (await s.execute(text(
        f"""SELECT {MINI_COLS}
            FROM anime_catalog c1 JOIN anime_catalog c2 ON c1.mal_id != c2.mal_id
            WHERE c1.mal_id = :i
              AND EXISTS (SELECT 1 FROM jsonb_array_elements_text(c1.genres) AS g(elem) WHERE c2.genres ? elem)
            ORDER BY c2.score DESC NULLS LAST LIMIT :n"""), {"i": mal_id, "n": limit})).all()
    return [_mini(r) for r in rows]
