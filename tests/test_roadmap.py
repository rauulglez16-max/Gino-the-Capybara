"""The coming soon page at /roadmap: its data file must stay valid and public-safe, and the page must show every item."""
import pytest

from gino import public, roadmap, timeline


def test_roadmap_file_is_valid():
    items = roadmap.load()  # raises ValueError with a clear message if an item is broken
    assert all(it["when"] in roadmap.WHEN for it in items)


def test_roadmap_is_public_safe():
    for it in roadmap.load():
        assert public.check(it["title"], it["text"]) is None, it["title"]


def test_built_things_leave_the_roadmap():
    done = {t["title"].lower() for t in timeline.load()}
    assert not [it["title"] for it in roadmap.load() if it["title"].lower() in done]


def test_page_shows_every_item_and_links():
    html = roadmap.page()
    for it in roadmap.load():
        assert roadmap.E(it["title"]) in html
    assert 'href="/timeline"' in html and "<script>" in html


def test_bad_item_is_refused(tmp_path, monkeypatch):
    f = tmp_path / "roadmap.json"
    f.write_text('[{"when": "tomorrow", "emoji": "x", "title": "t", "text": "t"}]', encoding="utf-8")
    monkeypatch.setattr(roadmap, "FILE", f)
    with pytest.raises(ValueError, match="when must be one of"):
        roadmap.load()


def test_linked_from_welcome_and_timeline():
    from gino import welcome
    assert 'href="/roadmap"' in timeline.page()
    assert 'href="/roadmap"' in welcome.page()
