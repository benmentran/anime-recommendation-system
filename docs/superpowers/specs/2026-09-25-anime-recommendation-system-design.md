# Anime Recommendation System — Frontend & BFF Redesign

**Date:** 2026-09-25  
**Status:** Approved for Implementation  
**Project:** netflix-movie-recommendation-system → anime-recommendation-system

---

## 1. Executive Summary

Transform the existing Netflix-clone (FastAPI + Jinja2) into a modern **anime recommendation system** with:
- **React SPA** (Vite + TypeScript + Tailwind) deployed on Vercel
- **FastAPI BFF** (`web_service`) serving JSON, aggregating Jikan (REST) + AniList (GraphQL) + internal recommend/feature services
- **User anime lists** (Watching/Completed/On-Hold/Dropped/Plan to Watch) as implicit feedback for model retraining
- **Hybrid recommendations** (CF + content-based) with "Why recommended" explainability UI

---

## 2. Architecture

```
┌─────────────────┐     HTTPS/JSON      ┌──────────────────┐
│  React SPA      │ ◀─────────────────▶ │  web_service     │
│  (Vercel)       │                     │  (BFF, :8000)    │
└─────────────────┘                     └────────┬─────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    ▼                            ▼                            ▼
             ┌──────────────┐            ┌──────────────┐            ┌──────────────────┐
             │ Jikan REST   │            │ AniList      │            │ Internal Services│
             │ (3 req/s)    │            │ GraphQL      │            │ (recommend,      │
             │ No auth      │            │ (public)     │            │  feature_retrieval)│
             └──────────────┘            └──────────────┘            └──────────────────┘
```

### 2.1 Component Responsibilities

| Component | Responsibility | Tech |
|-----------|----------------|------|
| **React SPA** | All UI, client state, server state cache | React 18, Vite, TS, Tailwind, TanStack Query, Zustand, React Router v6 |
| **web_service (BFF)** | Auth (JWT + Google OAuth), data aggregation, rate-limited anime API proxy, user list CRUD, recommendation proxy | FastAPI, Pydantic, httpx, tenacity, PostgreSQL, Redis |
| **anime_service (new)** | Jikan client (token-bucket rate limit), AniList GraphQL client, response mapping to internal schemas | Python, httpx, gql |
| **recommend_service** | Hybrid CF + content-based recommendations, `/recommendations/for-you`, `/recommendations/{anime_id}` | Existing + fixes |
| **feature_store_service** | Vectorize anime features (tags with weights from AniList, genres, studios, source) | Existing |
| **Airflow/DVC** | Incremental seasonal crawl, snapshot storage, feature materialization | Existing |

---

## 3. Data Sources & Mapping

### 3.1 Jikan (Primary — REST, no auth, 3 req/s / 60 req/min)

| Endpoint | Use Case | Key Fields |
|----------|----------|------------|
| `/anime/{id}/full` | Detail page | `title`, `title_japanese`, `synopsis`, `episodes`, `status`, `season`, `year`, `studios`, `source`, `genres`, `demographics`, `rating`, `score`, `scored_by`, `rank`, `popularity`, `favorites`, `trailer`, `images` |
| `/anime/{id}/recommendations` | "Why recommended" + similar | `entry.mal_id`, `entry.title`, `entry.images`, `entry.score`, `content` (user's reason) |
| `/seasons/{year}/{season}` | Seasonal browse | Paginated list |
| `/top/anime` | Top rated browse | Paginated list |
| `/search/anime` | Search | Query params: `q`, `genres`, `status`, `rating`, `order_by`, `sort` |

**Rate Limit Strategy:** Token bucket — 1 worker, 350ms minimum interval, rolling 60s window. Honor `Expires` header (24h cache).

### 3.2 AniList (Supplementary — GraphQL, public)

| Query | Use Case | Key Fields |
|-------|----------|------------|
| `Media(id: $id)` | Detail enrichment | `tags { name, category, isGeneralSpoiler, isMediaSpoiler, isAdult, rank }` — `rank` = relevance % (0-100) |
| `MediaList(userId: $id)` | User list sync (future) | `status`, `progress`, `score`, `repeat` |
| `Page { media(...) }` | Search with tag filters | `genres`, `tags`, `season`, `seasonYear`, `format`, `status` |

**Tag Weights:** `tag.rank` (0-100) → feature vector for content-based filtering. Example: `{"Isekai": 95, "Time Travel": 87, "Magic": 72}`

### 3.3 Internal Schema (Pydantic — BFF response)

```python
class TagWithWeight(BaseModel):
    name: str
    weight: int  # 0-100 from AniList rank

class AnimeMini(BaseModel):
    id: int
    title: str
    title_japanese: str | None
    image_url: str
    score: float | None
    year: int | None

class AnimeDetail(BaseModel):
    id: int
    title: str
    title_japanese: str | None
    synopsis: str
    episodes: int | None
    status: str  # "Finished Airing", "Currently Airing", "Not Yet Aired"
    season: str | None  # "winter", "spring", "summer", "fall"
    year: int | None
    studios: list[str]
    source: str  # "Manga", "Light Novel", "Original", "Visual Novel", "Game", "Other"
    genres: list[str]
    tags: list[TagWithWeight]
    demographics: list[str]
    rating: str  # "PG-13", "R", "G", etc.
    score: float | None
    scored_by: int | None
    rank: int | None
    popularity: int | None
    favorites: int | None
    trailer_url: str | None
    image_url: str
    recommendations: list[AnimeMini]  # from Jikan
    relations: list[AnimeRelation]    # prequel/sequel/side-story from AniList
```

---

## 4. Frontend Specification

### 4.1 Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Home | Hero + 3 sections: This Season (grid), Top Rated (grid), Trending (carousel) |
| `/anime/:id` | AnimeDetail | Full detail + recommendations carousel + "Why recommended" badges |
| `/search` | Search | Faceted filter sidebar + results grid (infinite scroll) |
| `/list` | UserList | 5 tabs (Watching/Completed/On-Hold/Dropped/Plan to Watch), drag-to-change-status |
| `/auth/signin` | SignIn | Email/password + Google OAuth button |
| `/auth/signup` | SignUp | Name, email, password |
| `/settings` | Settings | Theme toggle, password change, connected accounts |

### 4.2 Key Components

| Component | Location | Notes |
|-----------|----------|-------|
| `AnimeCard` | Shared | Poster, title, score badge, year, status chip; hover → quick actions (add to list, view detail) |
| `AnimeGrid` | Home, Search | Responsive grid (1/2/3/4/5 cols), infinite scroll via TanStack Query `useInfiniteQuery` |
| `RecommendationCarousel` | AnimeDetail | Horizontal scroll, each card shows "Why" badge |
| `WhyBadge` | RecommendationCarousel | Pill: "Because you liked **Isekai (95%)**" or "Users like you also watched" |
| `StatusChip` | AnimeCard, UserList | Color-coded: Watching=green, Completed=blue, On-Hold=yellow, Dropped=red, Plan=gray |
| `TagCloud` | AnimeDetail | Wrap tags with weight bars (visual % relevance) |
| `SeasonTabs` | Home | Winter/Spring/Summer/Fall tabs for seasonal browse |
| `FilterSidebar` | Search | Genre multi-select, year range, season, status, score slider, tag search |

### 4.3 State Management

| State | Tool | Scope |
|-------|------|-------|
| Server data (anime, recommendations, user list) | TanStack Query | Global cache, 5min stale, background refetch |
| Auth (token, user) | Zustand + localStorage persist | `useAuthStore` |
| UI (theme, modals, filter drawer) | Zustand | `useUIStore` |
| Form state (auth, list edit) | React Hook Form + Zod | Per-form |

### 4.4 Styling — Tailwind Config

```js
// tailwind.config.js
theme: {
  extend: {
    colors: {
      anilist: {
        bg: '#1d1d1f',
        card: '#28282b',
        border: '#3a3a3d',
        text: '#f5f5f5',
        textMuted: '#9a9a9a',
        accent: '#00a1d6',      // AniList blue
        accentHover: '#00bfff',
        green: '#2ecc71',       // Watching
        blue: '#3498db',        // Completed
        yellow: '#f39c12',      // On-Hold
        red: '#e74c3c',         // Dropped
        gray: '#95a5a6',        // Plan to Watch
      }
    },
    fontFamily: {
      sans: ['Inter', 'system-ui', 'sans-serif'],
    },
  }
}
```

**Dark mode only** (anime sites are dark-first). Light mode not required.

---

## 5. Backend BFF Specification

### 5.1 Routes (All JSON, `/api/v1` prefix)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/anime/trending` | Seasonal + top rated + trending (aggregated) | Optional |
| `GET` | `/anime/search` | Proxy to Jikan `/search/anime` + AniList tag filter | Optional |
| `GET` | `/anime/{id}` | Full detail (Jikan + AniList tags merged) | Optional |
| `GET` | `/anime/{id}/recommendations` | Jikan recommendations + internal hybrid | Optional |
| `GET` | `/recommendations/for-you` | Hybrid CF + content for logged-in user | Required |
| `GET` | `/list` | Get user's anime list (all statuses) | Required |
| `POST` | `/list` | Add anime to list | Required |
| `PATCH` | `/list/{anime_id}` | Update status/progress/score | Required |
| `DELETE` | `/list/{anime_id}` | Remove from list | Required |
| `POST` | `/auth/signin` | Email/password → JWT | Public |
| `POST` | `/auth/signup` | Register → JWT | Public |
| `POST` | `/auth/google` | Google OAuth → JWT | Public |
| `GET` | `/auth/me` | Validate token, return user | Required |

### 5.2 Database (PostgreSQL — replace TinyDB)

```sql
-- users (extends existing)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    google_id VARCHAR(100) UNIQUE,
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- user_anime_list (NEW)
CREATE TABLE user_anime_list (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    anime_id INTEGER NOT NULL,  -- Jikan MAL ID
    status VARCHAR(20) NOT NULL CHECK (status IN ('watching','completed','on_hold','dropped','plan_to_watch')),
    progress INTEGER DEFAULT 0,  -- episodes watched
    score INTEGER CHECK (score BETWEEN 1 AND 10),
    started_at DATE,
    finished_at DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, anime_id)
);

-- Index for recommend_service feature retrieval
CREATE INDEX idx_user_anime_list_user_status ON user_anime_list(user_id, status);
```

### 5.3 Rate Limiting (Jikan Client)

```python
# services/anime_service/clients/jikan_client.py
class JikanClient:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(1)
        self._last_request = 0
        self._min_interval = 0.35  # 350ms

    async def _rate_limited_get(self, url: str, params: dict):
        async with self._semaphore:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
            return await self._client.get(url, params=params)
```

---

## 6. Recommendation System Integration

### 6.1 Hybrid Endpoint: `GET /api/v1/recommendations/for-you`

**Input:** `user_id` (from JWT)  
**Output:** `RecommendationResponse`

```python
class RecommendationItem(BaseModel):
    anime: AnimeMini
    score: float  # 0-1 hybrid score
    reasons: list[RecommendationReason]

class RecommendationReason(BaseModel):
    type: Literal["collaborative", "content", "popularity", "trending"]
    description: str
    weight: float  # contribution to final score
    # For content: tag name + weight
    tag: str | None = None
    tag_weight: int | None = None
```

**Algorithm (existing + new):**
1. **Collaborative (CF):** User-item matrix from `user_anime_list` (implicit: status=completed/watching → positive) → ALS/implicit MF → top-N similar users → their highly-rated anime
2. **Content-based:** User's tag profile = weighted avg of `TagWithWeight` from completed/watching anime → cosine similarity with all anime tag vectors (from AniList)
3. **Hybrid:** `0.6 * CF_score + 0.4 * Content_score` (tunable)
4. **Explainability:** For each recommended anime, attach top 2 reasons with weights

### 6.2 Item-to-Item: `GET /api/v1/recommendations/{anime_id}`

**Source:** Jikan `/anime/{id}/recommendations` (community) + internal content-based similar (tag cosine)  
**Merge:** Dedupe by ID, prioritize Jikan (real user recs), supplement with content-based

---

## 7. Data Pipeline Updates

### 7.1 Airflow DAG: `fetch_anime_metadata_dag.py` (replaces `fetch_extract_metadata_dag.py`)

| Task | Description |
|------|-------------|
| `produce_anime_ids` | Generate MAL IDs: seasonal (current + next 2 seasons) + top 5000 + search "anime" |
| `fetch_jikan_details` | Rate-limited crawl → `data/raw/anime_jikan.ndjson` |
| `fetch_anilist_tags` | GraphQL batch (50 IDs/query) → `data/raw/anime_anilist.ndjson` |
| `merge_anime_data` | Join on MAL ID → `data/raw/anime_merged.ndjson` |
| `save_to_postgres` | Upsert into `anime_catalog` table (new) |
| `trigger_feature_store` | Call `feature_store_service` to recompute vectors |

**Incremental Strategy:** Run weekly. Only fetch IDs not in `anime_catalog` or updated > 7 days ago. Seasonal anime added automatically via `produce_anime_ids`.

### 7.2 DVC

- `data/raw/anime_merged.ndjson.dvc` — snapshot per crawl
- `data/processed/anime_features.parquet.dvc` — feature store output

---

## 8. Deployment

| Component | Platform | Config |
|-----------|----------|--------|
| React SPA | Vercel | `vercel.json` with rewrites to `/index.html`, env: `VITE_API_URL=https://api.yourdomain.com` |
| web_service | AKS (existing) | Docker, port 8000, env: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `GOOGLE_CLIENT_ID` |
| recommend_service | AKS (existing) | Docker, port 8005 |
| feature_retrieval_service | AKS (existing) | Docker, port 8006 |
| anime_service | AKS (new) | Docker, port 8007 (internal only) |
| PostgreSQL | WSL volume (dev) / Azure Database (prod) | Existing |
| Redis | Existing | Existing |

**CORS:** BFF allows `https://*.vercel.app` + `http://localhost:5173`

---

## 9. Implementation Phases

### Phase 1: Frontend Scaffold (Week 1)
- Vite + React + TS + Tailwind + Router + TanStack Query + Zustand + Axios
- Auth flow (signin/signup/me, JWT interceptors, protected routes)
- Layout: Header (logo, search, user menu), Footer, ThemeProvider
- Home page skeleton with AnimeGrid + AnimeCard

### Phase 2: BFF JSON API (Week 1-2)
- Strip Jinja2, templates/, static/ from `web_service`
- Add Pydantic schemas (`anime_schemas.py`)
- Implement `anime_router.py` (Jikan + AniList clients)
- Implement `list_router.py` (PostgreSQL CRUD)
- Fix `recommend_router.py` syntax errors, add hybrid endpoint
- Migrate `db.py` to PostgreSQL (SQLAlchemy or asyncpg)

### Phase 3: Anime Service Clients (Week 2)
- `services/anime_service/clients/jikan_client.py` (token bucket)
- `services/anime_service/clients/anilist_client.py` (GraphQL + gql)
- `services/anime_service/mappers.py` (Jikan + AniList → internal schemas)
- Unit tests with mocked responses

### Phase 4: Core UI Pages (Week 2-3)
- Home: Seasonal tabs + Top Rated + Trending grids
- AnimeDetail: Full layout + RecommendationCarousel + WhyBadge + TagCloud
- Search: FilterSidebar + infinite scroll grid
- UserList: 5 tabs, drag-to-reorder (dnd-kit), optimistic updates

### Phase 5: Recommendation UI (Week 3)
- "Why recommended" badges on RecommendationCarousel
- `/recommendations/for-you` integration on Home (personalized section)
- Loading skeletons, error boundaries, empty states

### Phase 6: Polish & Deploy (Week 3-4)
- Vercel deploy config, preview deployments
- E2E tests (Playwright): auth flow, browse, detail, list, recommend
- Accessibility audit (axe-core)
- Performance: Lighthouse > 90
- Documentation: README, API docs (OpenAPI from FastAPI)

---

## 10. Success Criteria

| Metric | Target |
|--------|--------|
| Lighthouse Performance | > 90 |
| Lighthouse Accessibility | > 95 |
| Time to Interactive (TTI) | < 3s on 3G |
| API p95 latency (BFF) | < 500ms |
| Recommendation relevance (offline MAP@10) | > 0.15 |
| User list adoption (DAU with ≥1 list item) | > 40% |

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Jikan rate limit blocks crawl | High | Medium | Token bucket + 24h cache + incremental crawl |
| AniList GraphQL schema changes | Low | Medium | Version-pinned queries, integration tests |
| Recommendation quality low | Medium | High | Offline eval pipeline, A/B test weights |
| Vercel CORS issues | Low | Low | BFF proxy all external calls |
| PostgreSQL migration data loss | Low | High | Backup + migration scripts + staging deploy first |

---

## 12. Out of Scope (Nice-to-Have)

- Reviews/forum/activity feed
- Episode tracking per anime (beyond progress count)
- Social features (follow users, compare lists)
- Native mobile app
- Real-time notifications
- Admin dashboard

---

## 13. Appendix: File Tree (Target)

```
anime-recommendation-system/
├── anime-frontend/                    # NEW
│   ├── src/
│   │   ├── components/                # AnimeCard, AnimeGrid, RecommendationCarousel, WhyBadge, TagCloud, StatusChip, FilterSidebar, SeasonTabs
│   │   ├── pages/                     # Home, AnimeDetail, Search, UserList, SignIn, SignUp, Settings
│   │   ├── hooks/                     # useAuth, useAnimeList, useRecommendations
│   │   ├── stores/                    # authStore, uiStore (Zustand)
│   │   ├── api/                       # axios instance, query keys, endpoints
│   │   ├── types/                     # TypeScript interfaces matching Pydantic
│   │   ├── utils/                     # formatters, constants
│   │   ├── styles/                    # globals.css, tailwind.css
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── vercel.json
│   └── .env.example
│
├── services/
│   ├── web_service/                   # BFF (MODIFIED)
│   │   ├── app.py                     # No Jinja2, no static mount
│   │   ├── routes/
│   │   │   ├── anime_router.py        # NEW
│   │   │   ├── list_router.py         # NEW
│   │   │   ├── recommend_router.py    # FIXED + extended
│   │   │   └── auth_router.py         # Existing (cleaned)
│   │   ├── schemas/
│   │   │   └── anime_schemas.py       # NEW
│   │   ├── db.py                      # PostgreSQL (SQLAlchemy)
│   │   ├── security.py                # Existing
│   │   ├── requirements.txt           # + sqlalchemy, asyncpg, httpx, tenacity, gql
│   │   └── Dockerfile
│   │
│   ├── anime_service/                 # NEW
│   │   ├── clients/
│   │   │   ├── jikan_client.py
│   │   │   └── anilist_client.py
│   │   ├── mappers.py
│   │   ├── schemas.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── recommend_service/             # EXISTING (FIXES)
│   │   └── routers/recommend_router.py
│   │
│   ├── feature_store_service/         # EXISTING
│   │   └── (add tag-weight vectorization)
│   │
│   └── ... (other existing services)
│
├── airflow/
│   └── dags/
│       └── fetch_anime_metadata_dag.py  # NEW (replaces fetch_extract_metadata_dag.py)
│
├── data/
│   ├── raw/
│   │   ├── anime_jikan.ndjson
│   │   ├── anime_anilist.ndjson
│   │   └── anime_merged.ndjson
│   └── processed/
│       └── anime_features.parquet
│
└── docs/
    └── superpowers/specs/
        └── 2026-09-25-anime-recommendation-system-design.md
```

---

**Spec Review:** ✅ Complete — ready for implementation plan.