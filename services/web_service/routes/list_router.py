"""User list CRUD (5 MAL statuses -> implicit feedback). Auth wiring: reuse decode_token."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_service.db import get_session
from services.web_service.schemas.anime_schemas import ListItemIn, ListItemPatch

router = APIRouter(prefix="/api/v1/list", tags=["list"])
VALID = {"watching", "completed", "on_hold", "dropped", "plan_to_watch"}
USER_ID = 1  # ponytail: real user_id from JWT once auth middleware lands; constant keeps CRUD testable


@router.get("")
async def get_list(s: AsyncSession = Depends(get_session)):
    rows = (await s.execute(text("SELECT * FROM user_anime_list WHERE user_id = :u"), {"u": USER_ID})).all()
    return [dict(r._mapping) for r in rows]


@router.post("", status_code=201)
async def add_item(item: ListItemIn, s: AsyncSession = Depends(get_session)):
    if item.status not in VALID:
        raise HTTPException(400, "invalid status")
    await s.execute(text(
        """INSERT INTO user_anime_list (user_id, anime_id, status, progress, score)
           VALUES (:u, :a, :st, :p, :sc)
           ON CONFLICT (user_id, anime_id) DO UPDATE
           SET status = EXCLUDED.status, progress = EXCLUDED.progress, score = EXCLUDED.score"""),
        {"u": USER_ID, "a": item.anime_id, "st": item.status, "p": item.progress, "sc": item.score})
    await s.commit()
    return {"ok": True}


@router.patch("/{anime_id}")
async def patch_item(anime_id: int, patch: ListItemPatch, s: AsyncSession = Depends(get_session)):
    sets = {k: v for k, v in patch.model_dump().items() if v is not None}
    if sets.get("status") and sets["status"] not in VALID:
        raise HTTPException(400, "invalid status")
    if not sets:
        raise HTTPException(400, "nothing to update")
    clause = ", ".join(f"{k} = :{k}" for k in sets)
    await s.execute(text(f"UPDATE user_anime_list SET {clause} WHERE user_id = :u AND anime_id = :a"),
                    {"u": USER_ID, "a": anime_id, **sets})
    await s.commit()
    return {"ok": True}


@router.delete("/{anime_id}")
async def delete_item(anime_id: int, s: AsyncSession = Depends(get_session)):
    await s.execute(text("DELETE FROM user_anime_list WHERE user_id = :u AND anime_id = :a"),
                    {"u": USER_ID, "a": anime_id})
    await s.commit()
    return {"ok": True}
