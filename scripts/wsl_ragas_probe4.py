import re

src = open("/root/.venv-rag/lib/python3.11/site-packages/ragas/evaluation.py").read()
m = re.search(r"^from .*Metric.*$|^import .*Metric.*$", src, re.M)
print("Metric import line:", m.group(0) if m else None)

from ragas.metrics.collections import Faithfulness

print("Faithfulness MRO:", [c.__module__ + "." + c.__name__ for c in Faithfulness.__mro__[:4]])
