"""Jikan-schema REST client: 1 worker, 350ms interval, rolling-60s cap, Retry-After/Expires.

Source defaults to Tenrai (Jikan v4-compatible schema): public Jikan API is
shutting down 2026-10-01 and 504s on all endpoints. Override with
ANIME_API_BASE_URL to point back at Jikan (https://api.jikan.moe/v4) if needed.
"""
import asyncio
import os
import time
from collections import deque
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

BASE_URL = os.getenv("ANIME_API_BASE_URL", "https://api.tenrai.org/v1")
MIN_INTERVAL = 0.35
MAX_PER_MINUTE = 60


class JikanClient:
    def __init__(self, timeout: int = 30):
        self._client = httpx.AsyncClient(base_url=BASE_URL, timeout=timeout)
        self._lock = asyncio.Semaphore(1)  # ponytail: single worker, no pool
        self._last = 0.0
        self._hits: deque[float] = deque()

    async def _throttle(self):
        async with self._lock:
            now = time.monotonic()
            wait = MIN_INTERVAL - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            # rolling 60s window
            cutoff = time.monotonic() - 60
            while self._hits and self._hits[0] < cutoff:
                self._hits.popleft()
            if len(self._hits) >= MAX_PER_MINUTE:
                await asyncio.sleep(self._hits[0] + 60 - time.monotonic() + 0.05)
            self._last = time.monotonic()
            self._hits.append(self._last)

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=30),
           retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)))
    async def get_anime_full(self, mal_id: int) -> tuple[dict, datetime]:
        await self._throttle()
        resp = await self._client.get(f"/anime/{mal_id}/full")
        if resp.status_code == 429:  # honor Retry-After then retry via tenacity
            await asyncio.sleep(float(resp.headers.get("Retry-After", "2")))
            raise httpx.HTTPStatusError("429", request=resp.request, response=resp)
        resp.raise_for_status()
        return resp.json().get("data", {}), self._expires_at(resp.headers.get("Expires"))

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=30),
           retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)))
    async def get_list(self, endpoint: str, params: dict | None = None) -> dict:
        """GET a paginated Jikan list endpoint (top/seasons/search). Same throttle/retry."""
        await self._throttle()
        resp = await self._client.get(endpoint, params=params or {})
        if resp.status_code == 429:
            await asyncio.sleep(float(resp.headers.get("Retry-After", "2")))
            raise httpx.HTTPStatusError("429", request=resp.request, response=resp)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _expires_at(header: str | None) -> datetime:
        if header:
            try:
                return parsedate_to_datetime(header)
            except (TypeError, ValueError):
                pass
        return datetime.now(timezone.utc) + timedelta(hours=24)

    async def close(self):
        await self._client.aclose()
