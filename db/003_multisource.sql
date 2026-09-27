-- Multi-source dimension: one schema, source-namespaced rating/popularity fields.
-- Fields that are NOT comparable across sources (scores, ranks, favourites)
-- stay separate per source instead of being merged into one. Applied manually
-- on existing DBs (initdb only runs this for fresh databases):
--   psql $DATABASE_URL -f db/003_multisource.sql
ALTER TABLE anime_catalog
    ADD COLUMN IF NOT EXISTS sources TEXT[] NOT NULL DEFAULT '{tenrai}',
    ADD COLUMN IF NOT EXISTS score_mal DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS scored_by_mal INTEGER,
    ADD COLUMN IF NOT EXISTS rank_mal INTEGER,
    ADD COLUMN IF NOT EXISTS popularity_mal INTEGER,
    ADD COLUMN IF NOT EXISTS score_anilist DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS favourites_anilist INTEGER,
    ADD COLUMN IF NOT EXISTS popularity_anilist INTEGER,
    ADD COLUMN IF NOT EXISTS tags_anilist JSONB NOT NULL DEFAULT '[]';

-- Backfill MAL-sourced columns from the raw Tenrai/MAL payloads.
UPDATE anime_catalog AS c SET
    score_mal = NULLIF(r.payload->>'score', '')::double precision,
    scored_by_mal = NULLIF(r.payload->>'scored_by', '')::int,
    rank_mal = NULLIF(r.payload->>'rank', '')::int,
    popularity_mal = NULLIF(r.payload->>'popularity', '')::int
FROM anime_raw AS r
WHERE r.mal_id = c.mal_id AND r.source IN ('jikan', 'tenrai');
