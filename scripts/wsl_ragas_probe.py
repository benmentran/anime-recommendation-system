from ragas.metrics.collections import (
    answer_correctness,
    faithfulness,
)

print("faithfulness:", type(faithfulness))
print("answer_correctness:", type(answer_correctness))
try:
    m = faithfulness()
    print("instantiated:", type(m), getattr(m, "name", None))
except Exception as e:
    print("call failed:", type(e).__name__, e)
