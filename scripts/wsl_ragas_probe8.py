from ragas.metrics import (
    answer_correctness,
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
from ragas.metrics.base import Metric

for m in (faithfulness, answer_relevancy, context_precision, context_recall,
          answer_correctness):
    print(type(m).__name__, isinstance(m, Metric))
