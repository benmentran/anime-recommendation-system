import inspect

from ragas.metrics.collections import (AnswerCorrectness, AnswerRelevancy,
                                       ContextPrecision, ContextRecall,
                                       Faithfulness)

for cls in (Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall,
            AnswerCorrectness):
    print(cls.__name__, inspect.signature(cls.__init__))
