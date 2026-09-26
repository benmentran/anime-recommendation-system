import os
import sys

print("PROBE_ALIVE")
print("HAS_KEY:", bool(os.getenv("OPENAI_API_KEY")))
print("ARGV:", sys.argv[1:])
