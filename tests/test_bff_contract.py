"""BFF JSON contract: health + router prefixes, no Jinja2."""
import sys

sys.path.insert(0, ".")
from fastapi.testclient import TestClient
from services.web_service.app import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"ok": True}


def test_api_prefixes_registered():
    paths = {r.path for r in app.routes}
    assert "/api/v1/anime/trending" in paths
    assert "/api/v1/list" in paths


def test_no_jinja_in_app():
    src = open("services/web_service/app.py").read()
    assert "Jinja2" not in src and "TemplateResponse" not in src
