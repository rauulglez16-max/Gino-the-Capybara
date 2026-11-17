"""What Gino publishes must not leak anything private, including words hidden inside his drawings."""
import time

import pytest
from fastapi import HTTPException

from gino import config, db, public, shop


def drawing(svg: str, title="Sunset") -> int:
    name = f"{int(time.time() * 1000)}-x.svg"
    (config.DATA_DIR / "creations" / name).write_text(svg, encoding="utf-8")
    return db.x("INSERT INTO creations(ts,kind,title,filename) VALUES(?,?,?,?)", (time.time(), "svg", title, name))


CLEAN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400"><circle cx="200" cy="200" r="90" fill="#fc0"/></svg>'
LEAKY = {
    "visible text": '<svg viewBox="0 0 400 400"><text x="10" y="20">For Raul</text></svg>',
    "title": '<svg viewBox="0 0 400 400"><title>my dad and me</title></svg>',
    "description": '<svg viewBox="0 0 400 400"><desc>painted for papa</desc></svg>',
    "comment": '<svg viewBox="0 0 400 400"><!-- call me +44 7700 900123 --><rect width="9" height="9"/></svg>',
    "metadata": '<svg viewBox="0 0 400 400"><metadata>owner: someone@example.com</metadata></svg>',
    "label": '<svg viewBox="0 0 400 400"><g aria-label="Raul\'s garden"><rect width="9" height="9"/></g></svg>',
    "split name": '<svg viewBox="0 0 400 400"><text><tspan>Ra</tspan><tspan>ul</tspan></text></svg>',
    "html entities": '<svg viewBox="0 0 400 400"><text>&#68;ad</text></svg>',
    "private word": '<svg viewBox="0 0 400 400"><text>Sunset over Valencia</text></svg>',
    "cdata": '<svg viewBox="0 0 400 400"><style><![CDATA[ /* dad */ ]]></style></svg>',
}


def test_clean_drawing_can_be_published():
    cid = drawing(CLEAN)
    assert public.write_page("My sun", "I drew the sun.", creation_id=cid).startswith("Published")


@pytest.mark.parametrize("where", list(LEAKY))
def test_private_words_inside_a_drawing_are_caught(where):
    cid = drawing(LEAKY[where])
    r = public.write_page("My drawing", "Look what I made.", creation_id=cid)
    assert r.startswith("Not published"), where


def test_shape_numbers_are_not_mistaken_for_phone_numbers():
    svg = '<svg viewBox="0 0 400 400"><path d="M +12 345 678 901 L 20 30"/><polygon points="+1 2345 6789 0"/></svg>'
    assert public.check(public.svg_text(svg)) is None


def test_private_words_list_works_in_text_too():
    assert public.check("Today I watched Luna the cat chase leaves") is not None
    assert public.check("Today I watched the moon") is None


def test_already_published_leaky_drawing_is_not_served():
    cid = drawing(CLEAN)
    public.write_page("Art", "My art.", creation_id=cid)
    assert public.art(cid).status_code == 200
    path = config.DATA_DIR / "creations" / db.q("SELECT filename FROM creations WHERE id=?", (cid,))[0]["filename"]
    path.write_text(LEAKY["visible text"], encoding="utf-8")
    with pytest.raises(HTTPException):
        public.art(cid)


@pytest.fixture
def open_shop(monkeypatch):
    calls = []
    monkeypatch.setattr(shop, "configured", lambda: True)
    monkeypatch.setattr(shop, "stripe", lambda *a, **k: calls.append(a) or {"id": "prod_1", "default_price": "price_1"})
    return calls


def test_shop_refuses_a_drawing_with_private_text_inside(open_shop):
    cid = drawing(LEAKY["label"], title="Garden")
    r = shop.list_item(cid, "Garden at dusk", "A quiet garden I painted one evening.", 3)
    assert r.startswith("Not listed") and open_shop == []


def test_shop_lists_a_clean_drawing(open_shop):
    cid = drawing(CLEAN)
    r = shop.list_item(cid, "Big sun", "A happy yellow sun to brighten a wall.", 3)
    assert "is for sale" in r and open_shop
