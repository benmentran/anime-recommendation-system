import os

from openai import OpenAI as SyncOpenAI
from ragas.embeddings import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.base import Metric
from ragas.metrics.collections import (AnswerCorrectness, AnswerRelevancy,
                                       ContextPrecision, ContextRecall,
                                       Faithfulness)

key = os.environ.get("OPENAI_API_KEY", "x")
sync_client = SyncOpenAI(api_key=key)
llm = llm_factory("gpt-4o-mini", client=sync_client)
emb = embedding_factory("openai", model="text-embedding-3-small", client=sync_client)
print("llm:", type(llm))
print("emb:", type(emb))
objs = [Faithfulness(llm=llm), AnswerRelevancy(llm=llm, embeddings=emb),
        ContextPrecision(llm=llm), ContextRecall(llm=llm),
        AnswerCorrectness(llm=llm, embeddings=emb)]
for o in objs:
    print(type(o).__name__, isinstance(o, Metric))
