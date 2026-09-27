import ragas

print("ragas file:", ragas.__file__)

from ragas.metrics.base import Metric
from ragas.metrics.collections import Faithfulness

print("Metric:", Metric)
import ragas.metrics.base as B

print("same module:", B.__file__)

try:
    m = Faithfulness(llm=None)
    print("constructed, isinstance Metric:", isinstance(m, Metric))
except Exception as e:
    print("construct failed:", type(e).__name__, e)
