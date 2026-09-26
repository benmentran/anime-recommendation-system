import asyncio
import sys

import httpx


async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("http://localhost:6333/collections/anime")
        r.raise_for_status()
        info = r.json()["result"]
        print("POINTS:", info["points_count"], flush=True)
        print("STATUS:", info["status"], flush=True)
        print("VECTORS:", info.get("vectors_count"), flush=True)


asyncio.run(main())
