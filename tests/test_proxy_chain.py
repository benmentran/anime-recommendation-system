"""BFF -> recommend_service proxy contract (downstream mocked, no network)."""
import sys

sys.path.insert(0, ".")

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from services.web_service.app import app

client = TestClient(app)


class FakeResp:
    status_code = 200
    text = ""

    def json(self):
        return {"answer": "ok", "candidates": [{"mal_id": 1, "title": "X"}]}


def test_ask_proxy_passthrough_shape():
    with patch("services.web_service.routes.rag_proxy_router.httpx.AsyncClient") as MC:
        inst = MC.return_value.__aenter__.return_value
        inst.post = AsyncMock(return_value=FakeResp())
        r = client.post("/api/v1/rag/ask", json={"query": "mecha?", "k": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "ok"
    assert body["candidates"][0]["mal_id"] == 1
    assert inst.post.call_args[0][0].endswith("/api/v1/rag/ask")


def test_ask_proxy_propagates_downstream_error():
    class Err:
        status_code = 503
        text = "model not loaded"

    with patch("services.web_service.routes.rag_proxy_router.httpx.AsyncClient") as MC:
        inst = MC.return_value.__aenter__.return_value
        inst.post = AsyncMock(return_value=Err())
        r = client.post("/api/v1/rag/ask", json={"query": "x"})
    assert r.status_code == 503
