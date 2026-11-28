"""Phones must not keep an old copy of Gino's code or model after an update."""
from fastapi.testclient import TestClient

from gino import server


def test_code_and_model_are_checked_again():
    c = TestClient(server.app)
    for path in ("/static/kit.js", "/static/world.js", "/static/models/gino.glb"):
        r = c.get(path)
        assert r.status_code == 200 and r.headers["cache-control"] == "no-cache", path
        again = c.get(path, headers={"If-None-Match": r.headers["etag"]})
        assert again.status_code == 304   # unchanged files cost almost nothing


def test_pages_load_the_current_world():
    for page in ("live.html", "index.html", "stream.html", "photo.html", "clip.html"):
        assert "/static/world.js?v=" in (server.STATIC / page).read_text(encoding="utf-8"), page
