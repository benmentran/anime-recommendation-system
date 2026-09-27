"""Vietnamese->English query translation for embedding (cached, EN pass-through).

Rationale (WS6/7): documents are English, queries often Vietnamese; translating
the short query is 100x cheaper than bilingual re-embedding of 5k documents.
"""
import os

from openai import AsyncOpenAI

from pipelines.rag_retrieval import detect_language

MODEL = os.getenv("TRANSLATE_MODEL", "gpt-4o")  # user decision 2026-09-27: gpt-4o, not mini
_cache: dict[str, str] = {}


async def translate_query(query: str, client: AsyncOpenAI | None = None) -> str:
    """Return English query. EN input passes through with no API call."""
    if query in _cache:
        return _cache[query]
    if detect_language(query) != "vi":
        _cache[query] = query
        return query
    own = client is not None
    oai = client or AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    try:
        r = await oai.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": (
                "Translate the user's anime search query to English. "
                "Keep anime titles, character names and loanwords unchanged. "
                "Reply with ONLY the translation.")},
                      {"role": "user", "content": query}],
            temperature=0, max_tokens=200)
        out = (r.choices[0].message.content or "").strip() or query
    except Exception:
        out = query  # fail-open: untranslated query still searchable
    finally:
        if not own:
            await oai.close()
    _cache[query] = out
    return out


def clear_cache():
    _cache.clear()
