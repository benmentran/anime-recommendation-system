"""RAGAS scoring on Windows (stable internet; no Qdrant needed at this stage).

Reads data/golden_dataset/ragas_samples.json (30 rows with user_input,
retrieved_contexts, response, reference, reference_contexts), scores the 5
RAGAS metrics with judge gpt-4o-mini, merges with retrieval stats, writes
data/golden_dataset/benchmark_results.json.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_correctness,
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-4o-mini")
# python scripts/run_ragas_score.py [--samples data/golden_dataset/ragas_samples_X.json --arm X]
# Không args = legacy: chấm slot chung, ghi top-level (chỉ dùng cho baseline).
SAMPLES = (sys.argv[sys.argv.index("--samples") + 1]
           if "--samples" in sys.argv
           else "data/golden_dataset/ragas_samples.json")
ARM = sys.argv[sys.argv.index("--arm") + 1] if "--arm" in sys.argv else None


def _load_dotenv():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

samples = json.loads((ROOT / SAMPLES).read_text(encoding="utf-8"))
print(f"samples={len(samples)}", flush=True)
ds = EvaluationDataset([SingleTurnSample(**{k: s[k] for k in (
    "user_input", "retrieved_contexts", "response", "reference",
    "reference_contexts")}) for s in samples])
llm = LangchainLLMWrapper(ChatOpenAI(model=JUDGE_MODEL))
emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))
result = evaluate(
    dataset=ds,
    metrics=[faithfulness, answer_relevancy, context_precision,
             context_recall, answer_correctness],
    llm=llm, embeddings=emb)
import math

rows = result.scores  # one dict per sample (NOT means!)
print(f"rows={len(rows)}", flush=True)
means, table = {}, []
for r in rows:
    table.append({k: (None if v is None or (isinstance(v, float) and math.isnan(v)) else v)
                  for k, v in r.items()})
keys = [k for k in rows[0] if k != "id"]
for k in keys:
    vals = [r[k] for r in table if isinstance(r[k], (int, float))]
    means[k] = round(sum(vals) / len(vals), 4) if vals else None
    print(f"{k}: mean={means[k]} n={len(vals)}/{len(table)}", flush=True)
scores = means
print("RAGAS:", json.dumps(scores, ensure_ascii=False), flush=True)

prev = {}
res_path = ROOT / "data/golden_dataset/benchmark_results.json"
if res_path.exists():
    prev = json.loads(res_path.read_text(encoding="utf-8"))
block = {"ragas": scores, "ragas_per_row": table, "judge_model": JUDGE_MODEL,
         "generator_model": "gpt-4o", "embed_model": "text-embedding-3-small"}
if ARM:
    arm_block = prev.get(ARM, {})
    arm_block.update(block)
    prev[ARM] = arm_block
else:
    prev.update(block)
res_path.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
print("SAVED", res_path, flush=True)
