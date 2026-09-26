import asyncio
import sys

import httpx

QUERY = sys.argv[1] if len(sys.argv) > 1 else "mecha anime with heavy politics"
K = int(sys.argv[2]) if len(sys.argv) > 2 else 5


async def main():
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            "http://localhost:8001/api/v1/rag/ask",
            json={"query": QUERY, "k": K})
        print("STATUS:", r.status_code, flush=True)
        body = r.json()
        print("CANDIDATES:", [(x["title"], x.get("score")) for x in body.get("candidates", [])],
              flush=True)
        print("=" * 60)
        print(body.get("answer", body))


asyncio.run(main())
