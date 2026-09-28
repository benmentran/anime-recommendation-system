from pydantic import BaseModel


class TagWithWeight(BaseModel):
    name: str
    weight: int = 0


class AnimeMini(BaseModel):
    id: int
    title: str
    title_japanese: str | None = None
    image_url: str | None = None
    score: float | None = None
    year: int | None = None


class AnimeDetail(BaseModel):
    id: int
    title: str
    title_japanese: str | None = None
    synopsis: str | None = None
    episodes: int | None = None
    status: str | None = None
    season: str | None = None
    year: int | None = None
    studios: list[str] = []
    source: str | None = None
    genres: list[str] = []
    tags: list[TagWithWeight] = []
    score: float | None = None
    image_url: str | None = None


class GenreCount(BaseModel):
    name: str
    count: int


class ListItemIn(BaseModel):
    anime_id: int
    status: str = "plan_to_watch"
    progress: int = 0
    score: int | None = None


class ListItemPatch(BaseModel):
    status: str | None = None
    progress: int | None = None
    score: int | None = None
