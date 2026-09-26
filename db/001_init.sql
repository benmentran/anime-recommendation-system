-- P0 init: anime persistence (auto-applied via /docker-entrypoint-initdb.d)
CREATE TABLE IF NOT EXISTS anime_raw (
    mal_id INTEGER PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'jikan',
    payload JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours'
);
CREATE INDEX IF NOT EXISTS idx_anime_raw_expires ON anime_raw(expires_at);

CREATE TABLE IF NOT EXISTS anime_catalog (
    mal_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    title_japanese TEXT,
    synopsis TEXT,
    episodes INTEGER,
    status TEXT,
    season TEXT,
    year INTEGER,
    studios JSONB NOT NULL DEFAULT '[]',
    source TEXT,
    genres JSONB NOT NULL DEFAULT '[]',
    tags JSONB NOT NULL DEFAULT '[]',
    score DOUBLE PRECISION,
    image_url TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    google_id VARCHAR(100) UNIQUE,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_anime_list (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    anime_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('watching','completed','on_hold','dropped','plan_to_watch')),
    progress INTEGER NOT NULL DEFAULT 0,
    score INTEGER CHECK (score BETWEEN 1 AND 10),
    started_at DATE,
    finished_at DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, anime_id)
);
CREATE INDEX IF NOT EXISTS idx_user_anime_list_user_status ON user_anime_list(user_id, status);

CREATE TABLE IF NOT EXISTS etl_watermark (
    pipeline TEXT PRIMARY KEY,
    last_run TIMESTAMPTZ NOT NULL DEFAULT NOW() - INTERVAL '30 days'
);
INSERT INTO etl_watermark (pipeline) VALUES ('anime_transform')
ON CONFLICT (pipeline) DO NOTHING;
