"""Gino's live habitat: anyone can watch him in his 3D world at /live, nobody can talk to him there.

Visitors only ever see a small, filtered slice of his state: where he is, what he's doing, how he feels,
his habitat and the drawings he already put on his public website. No chats, no thoughts, no memories,
no journal, nothing about dad. Every bit of text Gino wrote goes through public.check() first, the same
filter his public website uses. There are no write endpoints here: chatting, gifts and petting stay
behind the password on the private page.
"""
import re
import threading
import time

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from . import config, db, public, vitals

router = APIRouter()
STATIC = config.ROOT / "gino" / "static"
CACHE_SECONDS = 5  # however many people watch, the database is read at most once every few seconds

# The page loads three.js from jsdelivr; everything else comes from this server. No forms, no framing.
PAGE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                               "connect-src 'self'; img-src 'self' data: blob:; style-src 'unsafe-inline'; "
                               "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "public, max-age=300",
}
API_HEADERS = {"Cache-Control": f"public, max-age={CACHE_SECONDS}", "X-Content-Type-Options": "nosniff"}

_cache: dict = {"at": 0.0, "data": None}
_lock = threading.Lock()


def _clean(text, limit: int, fallback: str = "") -> str:
    """Gino's own words, if they're safe for the whole world. Otherwise a harmless fallback."""
    text = " ".join(str(text or "").split())[:limit]
    if not text or public.check(text):
        return fallback
    return text


def _item_name(name: str, kind: str) -> str:
    safe = _clean(name, 80)
    if safe:
        return safe
    # e.g. "Dad's bench": drop the private words and keep the rest if what's left is fine
    stripped = public._FAMILY.sub("", str(name or ""))
    dad = (config.DAD_NAME or "").strip()
    if len(dad) >= 2:
        stripped = re.sub(rf"\b{re.escape(dad)}\b", "", stripped, flags=re.I)
    stripped = re.sub(r"(^|\s)['’]s\b", " ", stripped).strip(" -'’")
    return _clean(stripped, 80) or (kind.replace("_", " ") if kind else "something Gino made")


def _hour(now) -> float:
    return round(now.hour + now.minute / 60, 3)


def build() -> dict:
    from .brain import local_now, mind_lock  # imported late, like public.py does
    body = vitals.load()
    now = time.time()
    asleep = vitals.is_asleep(body, now)
    habitat = []
    for it in db.q("SELECT id,name,emoji,x,y,description,kind,color,size FROM habitat ORDER BY id"):
        kind = it["kind"] or ""
        habitat.append({
            "id": it["id"], "x": it["x"], "y": it["y"], "kind": kind, "size": it["size"],
            "name": _item_name(it["name"], kind),
            "emoji": _clean(it["emoji"], 8),
            "color": it["color"] if re.fullmatch(r"#[0-9a-fA-F]{6}", it["color"] or "") else "",
            "description": _clean(it["description"], 200),
        })
    # only drawings he already chose to show on a public page (served by /blog/art/<id>.svg)
    art = [f"/blog/art/{r['id']}.svg" for r in db.q(
        "SELECT DISTINCT c.id, c.ts FROM creations c JOIN posts p ON p.creation_id=c.id "
        "WHERE p.kind='page' AND c.kind='svg' ORDER BY c.ts DESC LIMIT 6")]
    pos = body.get("pos", [7, 5])
    local = local_now()
    return {
        "pos": [int(pos[0]), int(pos[1])],
        "asleep": asleep,
        "thinking": mind_lock.locked(),
        "activity": "napping" if asleep else _clean(body.get("activity"), 80, "pottering about"),
        "emotion": _clean(body.get("emotion"), 30, "calm"),
        "vitals": vitals.snapshot(body),
        "weather": vitals.weather(local),
        "local_hour": _hour(local),
        "age_days": round((now - body.get("born", now)) / 86400, 1),
        "habitat": habitat,
        "art": art,
    }


def state() -> dict:
    with _lock:
        if _cache["data"] is None or time.time() - _cache["at"] > CACHE_SECONDS:
            _cache["data"], _cache["at"] = build(), time.time()
        return _cache["data"]


@router.get("/live", response_class=HTMLResponse)
def live_page():
    return HTMLResponse((STATIC / "live.html").read_text(encoding="utf-8"), headers=PAGE_HEADERS)


@router.get("/api/live")
def live_state():
    return JSONResponse(state(), headers=API_HEADERS)
