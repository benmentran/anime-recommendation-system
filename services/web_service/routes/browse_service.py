from fastapi import APIRouter, Request, Cookie
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from services.trending_api import TrendingService
from services.tv_api import TVService
from services.movie_api import MovieService
from app.security import decode_token


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/browse", response_class=HTMLResponse)
async def browse(request: Request, token: str = Cookie(None)):
    user = decode_token(token)
    if not user:
        return templates.TemplateResponse("unauthorized.html", {"request": request}, status_code=403)

    trending_service = TrendingService()
    tv_service = TVService()
    movie_service = MovieService()

    trending_movies = (
        (await trending_service.fetch_trending_movies())["results"][:8] +
        (await movie_service.fetch_popular())["results"][:4] +
        (await movie_service.fetch_top_rated())["results"][:4]
    )
    trending_tv = (
        (await trending_service.fetch_trending_tv())["results"][:8] +
        (await tv_service.fetch_popular_tv())["results"][:4] +
        (await tv_service.fetch_top_rated_tv())["results"][:4]
    )

    return templates.TemplateResponse(
        "browse.html",
        {
            "request": request,
            "trending_movies": trending_movies,
            "trending_tv": trending_tv,
            "user": {"display_name": user.get("display_name", "User")},
        }
    )