import asyncio
import os
import sys

sys.path.insert(0, "/mnt/f/netflix-movie-recommendation-system")


async def main():
    print("S1 start", flush=True)
    from openai import AsyncOpenAI

    oai = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", "x"))
    print("S2 client built", flush=True)
    emb = await oai.embeddings.create(model="text-embedding-3-small", input=["hello"])
    print("S3 embedded dim=", len(emb.data[0].embedding), flush=True)
    import asyncpg

    conn = await asyncpg.connect("postgresql://anime:animepass@localhost:5432/anime")
    print("S4 pg connected", flush=True)
    n = await conn.fetchval("SELECT COUNT(*) FROM anime_catalog")
    print("S5 catalog rows=", n, flush=True)
    await conn.close()
    import httpx

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("http://localhost:6333/healthz")
        print("S6 qdrant:", r.text.strip(), flush=True)


asyncio.run(main())
print("S_ALL_OK", flush=True)
