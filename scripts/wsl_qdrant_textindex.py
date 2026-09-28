import asyncio

import httpx

URL = "http://localhost:6333"


async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.put(f"{URL}/collections/anime/index",
                        json={"field_name": "genres", "field_schema": "text"})
        print("create-index:", r.status_code, r.text[:200], flush=True)
        # verify with a filtered probe search
        r = await c.post(f"{URL}/collections/anime/points/search",
                         json={"vector": [0.0] * 1536, "limit": 3,
                               "filter": {"must": [{"key": "genres",
                                                    "match": {"text": "Mecha"}}]},
                               "with_payload": ["title"]})
        print("probe:", r.status_code, r.text[:300], flush=True)


asyncio.run(main())
