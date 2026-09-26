"""Prompt construction for RAG ask (pure, testable, no network)."""
from pipelines.rag_retrieval import detect_language

SYSTEM_PROMPT = (
    "You are an anime recommendation expert. Use ONLY the candidate information "
    "(Context) below. Pick the 2 titles that best fit the user's request, explain "
    "why each fits, and compare how they differ. Reply in the same language as "
    "the user query. If no candidate fits, say so honestly instead of inventing details."
)


def build_messages(query: str, candidates: list[dict], lang: str | None = None) -> list[dict]:
    """OpenAI chat messages: system instruction + query + retrieved context.

    `lang` auto-detected (vi/en heuristic) when omitted; the system message
    pins the output language explicitly (fixes wrong-language answers).
    """
    blocks = []
    for i, c in enumerate(candidates, 1):
        blocks.append(
            f"{i}. Name: {c.get('title')}\n"
            f"   Genres: {c.get('genres')}\n"
            f"   Summary: {c.get('synopsis')}\n"
            f"   Year: {c.get('year')} (score: {c.get('score')})"
        )
    context = "\n\n".join(blocks) if blocks else "(no candidates retrieved)"
    lang = lang or detect_language(query)
    lang_pin = ("Respond ONLY in Vietnamese. Trả lời CHỈ bằng tiếng Việt."
                if lang == "vi" else "Respond ONLY in English.")
    return [
        {"role": "system", "content": f"{SYSTEM_PROMPT} {lang_pin}"},
        {"role": "user",
         "content": f"[User Query]\n{query}\n\n[Context - Top {len(candidates)} Retrieved Items]\n{context}"},
    ]
