"""AniList GraphQL client: batch 50 IDs/query, plain httpx (no gql dep)."""
import asyncio

import httpx

URL = "https://graphql.anilist.co"
QUERY = """
query ($ids: [Int]) {
  Page(perPage: 50) {
    media(id_in: $ids, type: ANIME) {
      id
      tags { name rank category isMediaSpoiler }
      relations { edges { relationType } node { idMal title { romaji } } }
    }
  }
}
"""


async def fetch_tags_batch(ids: list[int], timeout: int = 30) -> list[dict]:
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        for i in range(0, len(ids), 50):
            chunk = ids[i:i + 50]
            r = await client.post(URL, json={"query": QUERY, "variables": {"ids": chunk}})
            r.raise_for_status()
            pages = r.json()["data"]["Page"]["media"] or []
            out.extend(pages)
    return out


TOP_QUERY = """
query ($page: Int, $season: MediaSeason, $seasonYear: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    media(sort: POPULARITY_DESC, type: ANIME, season: $season, seasonYear: $seasonYear) {
      idMal
    }
  }
}
"""


MEDIA_QUERY = """
query ($ids: [Int]) {
  Page(perPage: 50) {
    media(idMal_in: $ids, type: ANIME) {
      idMal
      tags { name rank isMediaSpoiler }
      averageScore
      popularity
      favourites
      description
      genres
    }
  }
}
"""


async def fetch_media_batch(mal_ids: list[int], timeout: int = 30) -> list[dict]:
    """Full media rows (tags/scores/description) for enrichment, 50 IDs/call.

    Paced for the 90 req/min shared quota; retries transient failures.
    Returns raw media dicts keyed by idMal (dedupe by caller).
    """
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        for i in range(0, len(mal_ids), 50):
            chunk = mal_ids[i:i + 50]
            last_error: Exception | None = None
            for attempt in range(4):
                try:
                    r = await client.post(
                        URL, json={"query": MEDIA_QUERY, "variables": {"ids": chunk}})
                    if r.status_code == 429:
                        await asyncio.sleep(int(r.headers.get("Retry-After", "60")))
                        continue
                    r.raise_for_status()
                    last_error = None
                    break
                except Exception as e:  # noqa: BLE001 - retry then propagate
                    last_error = e
                    await asyncio.sleep(2 * (attempt + 1))
            if last_error is not None:
                raise last_error
            out.extend(r.json()["data"]["Page"]["media"] or [])
            await asyncio.sleep(0.8)
    return out


async def fetch_top_mal_ids(limit: int = 5000, season: str | None = None,
                            season_year: int | None = None,
                            timeout: int = 30) -> list[int]:
    """Top MAL IDs via AniList (primary discovery source; Jikan list endpoints 504).

    90 req/min limit -> 0.7s pacing. idMal can be null (skip those).
    """
    ids: list[int] = []
    page = 1
    async with httpx.AsyncClient(timeout=timeout) as client:
        while len(ids) < limit:
            # AniList caps page depth at 5000 entries: page 100 is the last fetchable.
            if (page - 1) * 50 >= 5000:
                break
            variables: dict = {"page": page}
            if season:
                variables.update(season=season.upper(), seasonYear=season_year)
            last_error: Exception | None = None
            for attempt in range(4):
                try:
                    r = await client.post(URL, json={"query": TOP_QUERY, "variables": variables})
                    if r.status_code == 429:
                        await asyncio.sleep(int(r.headers.get("Retry-After", "60")))
                        continue
                    if r.status_code == 400 and "Page depth" in r.text:
                        last_error = None
                        page = 10**9  # sentinel: depth cap hit, stop gracefully
                        break
                    r.raise_for_status()
                    last_error = None
                    break
                except Exception as e:  # noqa: BLE001 - network flakiness, retry then propagate
                    last_error = e
                    await asyncio.sleep(2 * (attempt + 1))
            if last_error is not None:
                raise last_error
            if page >= 10**9:
                break
            payload = r.json()["data"]["Page"]
            for m in payload["media"] or []:
                if m.get("idMal") is not None and len(ids) < limit:
                    ids.append(m["idMal"])
            if not payload["pageInfo"]["hasNextPage"]:
                break
            page += 1
            await asyncio.sleep(1.0)  # stay well under 90 req/min shared quota
    return ids
