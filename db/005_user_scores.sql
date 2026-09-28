-- Jikan user scores for real CF (PART A). Independent from app users:
-- user_id is the Jikan username (TEXT), no FK to users(id).
-- NOTE: Jikan animelist entries carry no score timestamp, so scored_at is the
-- ingestion time (loaded_at default). Time-split preserves relative load order,
-- but scored_at is NOT "the day the user really scored it".
-- Apply on existing DBs: psql $DATABASE_URL -f db/005_user_scores.sql
CREATE TABLE IF NOT EXISTS user_scores (
    user_id TEXT NOT NULL,
    anime_id INTEGER NOT NULL,
    score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 10),
    scored_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, anime_id)
);
CREATE INDEX IF NOT EXISTS idx_user_scores_user ON user_scores (user_id);
CREATE INDEX IF NOT EXISTS idx_user_scores_anime ON user_scores (anime_id);
CREATE INDEX IF NOT EXISTS idx_user_scores_scored ON user_scores (scored_at);
