import asyncio
import sys

print("VERSION:", sys.version, flush=True)
print("PREFIX:", sys.prefix, flush=True)


async def main():
    print("LOOP_ALIVE", flush=True)


asyncio.run(main())
print("LOOP_DONE", flush=True)
