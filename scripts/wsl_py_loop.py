import asyncio
import sys

print("A1 before run", flush=True, file=sys.stderr)


async def main():
    print("A2 in main", flush=True, file=sys.stderr)
    await asyncio.sleep(0.1)
    print("A3 after sleep", flush=True, file=sys.stderr)


try:
    asyncio.run(main())
    print("A4 run returned", flush=True, file=sys.stderr)
except BaseException as e:
    print(f"A5 raised {type(e).__name__}: {e}", flush=True, file=sys.stderr)
    raise
