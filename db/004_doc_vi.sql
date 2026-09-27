-- Bilingual docs: Vietnamese translation of the EN retrieval document.
-- Filled by pipelines/translate_docs.py (gpt-4o-mini, resumable).
-- Applied manually on existing DBs (initdb only runs this for fresh databases):
--   psql $DATABASE_URL -f db/004_doc_vi.sql
ALTER TABLE anime_catalog ADD COLUMN IF NOT EXISTS doc_vi TEXT;
