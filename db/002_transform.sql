-- P2 SQL-first transform: 0 Python RAM, incremental via watermark.
-- Payload is raw Tenrai/Jikan /full JSON (nested); normalize here to the flat
-- catalog shape (same contract as services/anime_service/mappers.to_catalog).
-- tags come from a later AniList enrichment step (default []).
INSERT INTO anime_catalog (mal_id, title, title_japanese, synopsis, episodes, status,
    season, year, studios, source, genres, tags, score, image_url, updated_at)
SELECT
    mal_id,
    COALESCE(payload->>'title', 'Anime ' || mal_id),
    payload->>'title_japanese',
    payload->>'synopsis',
    NULLIF(payload->>'episodes', '')::int,
    payload->>'status',
    payload->>'season',
    NULLIF(payload->>'year', '')::int,
    COALESCE(
        (SELECT jsonb_agg(e->>'name')
         FROM jsonb_array_elements(COALESCE(payload->'studios', '[]')) AS e
         WHERE e->>'name' IS NOT NULL),
        '[]'::jsonb),
    payload->>'source',
    COALESCE(
        (SELECT jsonb_agg(DISTINCT e->>'name')
         FROM jsonb_array_elements(
             COALESCE(payload->'genres', '[]') || COALESCE(payload->'themes', '[]')
             || COALESCE(payload->'demographics', '[]') || COALESCE(payload->'explicit_genres', '[]')
         ) AS e
         WHERE e->>'name' IS NOT NULL),
        '[]'::jsonb),
    COALESCE(payload->'tags', '[]'),
    NULLIF(payload->>'score', '')::double precision,
    COALESCE(payload->'images'->'jpg'->>'large_image_url',
             payload->'images'->'jpg'->>'image_url',
             payload->'images'->'webp'->>'large_image_url'),
    NOW()
FROM anime_raw
WHERE fetched_at > (SELECT last_run FROM etl_watermark WHERE pipeline = 'anime_transform')
ON CONFLICT (mal_id) DO UPDATE SET
    title = EXCLUDED.title, title_japanese = EXCLUDED.title_japanese,
    synopsis = EXCLUDED.synopsis, episodes = EXCLUDED.episodes,
    status = EXCLUDED.status, season = EXCLUDED.season, year = EXCLUDED.year,
    studios = EXCLUDED.studios, source = EXCLUDED.source, genres = EXCLUDED.genres,
    tags = EXCLUDED.tags, score = EXCLUDED.score, image_url = EXCLUDED.image_url,
    updated_at = NOW();
UPDATE etl_watermark SET last_run = NOW() WHERE pipeline = 'anime_transform';
