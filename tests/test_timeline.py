"""The story timeline at /timeline: its data file must stay valid, and the page must render every entry."""
import datetime as dt

from gino import timeline


def test_timeline_file_is_valid():
    items = timeline.load()  # raises ValueError with a clear message if an entry is broken
    assert items[0]["date"] <= items[-1]["date"]


def test_page_shows_every_moment():
    html = timeline.page(today=dt.date(2026, 11, 17))
    for it in timeline.load():
        assert timeline.E(it["title"]) in html
    assert "Day 1" in html and "<script>" in html
