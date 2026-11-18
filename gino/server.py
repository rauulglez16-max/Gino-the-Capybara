"""Gino's home on the web: a small server that keeps him alive and lets dad visit."""
import asyncio
import contextlib
import logging
import re
import secrets
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import (artstyle, brain, clips, config, db, dreams, live, public, roadmap, shop, telegram, tiktok, timeline, vitals,
               welcome, whatsapp)

log = logging.getLogger("gino")
STATIC = config.ROOT / "gino" / "static"
from . import recap  # noqa: E402  ("since your last visit")


def shop_news() -> None:
    """Every few minutes, ask Stripe about new sales and tell Gino (and dad's phone) about them."""
    if not config.STRIPE_KEY:
        return
    shop.check_sales()
    with brain.mind_lock:
        sold = shop.news_for_gino()
        if not sold:
            return
        body = vitals.load()
        body["fun"] = vitals.clamp(body["fun"] + min(30, 10 * len(sold)))
        body["social"] = vitals.clamp(body["social"] + 5)
        vitals.save(body)
    telegram.send("🛒 Gino's shop: someone bought " + ", ".join(f"'{t}'" for t in sold)
                  + ". The money is in your Stripe account.")


async def life_loop():
    """Gino's heartbeat: keeps his body ticking and gives him turns when he wants them."""
    await asyncio.sleep(2)
    last_shop = 0.0
    while True:
        try:
            await asyncio.to_thread(clips.maybe_auto)  # his daily video, filmed in the background
        except Exception:
            log.exception("Starting today's video failed; trying again later")
        try:
            if time.time() - last_shop > 600 and not brain.mind_lock.locked():
                last_shop = time.time()
                await asyncio.to_thread(shop_news)
        except Exception:
            log.exception("Checking the shop's sales failed; trying again later")
        try:
            if not brain.mind_lock.locked():
                body = vitals.tick(vitals.load())
                vitals.save(body)
                now = time.time()
                if dreams.due(body, now):
                    await asyncio.to_thread(dreams.dream_now)
                elif not vitals.is_asleep(body, now) and now >= body.get("next_wake", 0):
                    await asyncio.to_thread(brain.take_turn)
        except Exception:
            log.exception("Gino's turn failed; trying again in a few minutes")
            with contextlib.suppress(Exception):
                b = vitals.load()
                b["next_wake"] = time.time() + 300
                vitals.save(b)
                db.event("mind", "Gino got confused for a moment (an error happened). He'll try again soon.")
        await asyncio.sleep(20)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    vitals.save(vitals.load())
    if whatsapp.enabled():
        log.info("Gino's WhatsApp line is on.")
    mode = "practice brain (no API key)" if config.FAKE_BRAIN else config.MODEL
    log.info("Gino is awake. Brain: %s. Daily budget: $%.2f", mode, config.DAILY_BUDGET_USD)
    task = asyncio.create_task(life_loop())
    phone = telegram.start()  # dad's phone line, if set up
    yield
    task.cancel()
    if phone:
        phone.set()


app = FastAPI(title="Gino", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.include_router(welcome.router)  # /: the welcome page that introduces Gino to everyone
app.include_router(timeline.router)  # /timeline: Gino's story so far, from gino/timeline.json
app.include_router(roadmap.router)  # /roadmap: what's coming next for Gino, from gino/roadmap.json
app.include_router(public.router)  # Gino's public website at /blog: no password, only what he chose to publish
app.include_router(shop.router)  # /blog/shop: Gino's drawings for sale; payments happen on Stripe's own checkout
app.include_router(artstyle.router)  # /blog/periods: his art periods, with drawings he already made public
app.include_router(live.router)  # /live: anyone can watch his 3D world, nobody can talk to him there
app.include_router(whatsapp.router)  # WhatsApp webhook: only signed requests from Meta, only dad's number


def auth(request: Request):
    if not config.PASSWORD:
        return
    given = request.headers.get("x-gino-key") or request.query_params.get("key") or ""
    if not secrets.compare_digest(given, config.PASSWORD):
        raise HTTPException(401, "Gino doesn't know you.")


@app.get("/private", response_class=HTMLResponse)
def index():  # dad's private page (chat, gifts, petting); its API calls need the password
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/state", dependencies=[Depends(auth)])
def state():
    body = vitals.load()
    now = time.time()
    recap.seen(now)  # dad is here
    return {
        "vitals": vitals.snapshot(body),
        "emotion": body.get("emotion"), "emotion_intensity": body.get("emotion_intensity"),
        "emotion_reason": body.get("emotion_reason"), "thought": body.get("thought"),
        "activity": body.get("activity"), "asleep": vitals.is_asleep(body, now),
        "thinking": brain.mind_lock.locked(),
        "next_wake_in": max(0, int(body.get("next_wake", now) - now)),
        "pantry": body.get("pantry", {}), "pos": body.get("pos", [7, 5]),
        "age_days": round((now - body.get("born", now)) / 86400, 2),
        "self": db.get("self", {}),
        "habitat": db.q("SELECT id,ts,name,emoji,x,y,description,kind,color,size,story,origin FROM habitat ORDER BY id"),
        "goals": db.q("SELECT id,title,why,steps,progress,status FROM goals ORDER BY status='active' DESC, updated DESC LIMIT 30"),
        "brain": "practice" if config.FAKE_BRAIN else config.MODEL,
        "spent_today": round(brain.spent_today(), 3), "budget": config.DAILY_BUDGET_USD,
        "foods": {k: v[2] for k, v in vitals.FOODS.items()},
        "weather": vitals.weather(brain.local_now()),
        "art": [r["filename"] for r in db.q("SELECT filename FROM creations WHERE kind='svg' ORDER BY ts DESC LIMIT 6")],
    }


@app.get("/api/recap", dependencies=[Depends(auth)])
def since_last_visit():
    """'Since your last visit...': what Gino did while dad was away (free: built from his own records)."""
    return recap.for_dad()


@app.get("/api/life", dependencies=[Depends(auth)])
def life():
    """Keepsakes with stories, dream inventions, time capsules and art periods, for dad's private page.
    A capsule's contents stay sealed (even from dad) until Gino digs it up."""
    caps = []
    for c in db.q("SELECT * FROM capsules ORDER BY ts DESC"):
        sealed = c["opened"] is None
        caps.append({"id": c["id"], "ts": c["ts"], "open_after": c["open_after"], "opened": c["opened"],
                     **({} if sealed else {k: c[k] for k in ("favourite", "prediction", "letter", "reflection")})})
    return {
        "keepsakes": db.q("SELECT id,ts,name,emoji,story,origin FROM habitat WHERE story!='' ORDER BY ts DESC"),
        "inventions": db.q("SELECT i.id,i.ts,i.name,i.idea,i.emoji,i.status,i.sessions,i.needed,i.twist,i.opinion,"
                           "i.log,c.filename AS sketch FROM inventions i LEFT JOIN creations c ON c.id=i.sketch_id "
                           "ORDER BY i.ts DESC"),
        "capsules": caps,
        "periods": artstyle.overview(public_only=False),
    }


@app.get("/api/feed", dependencies=[Depends(auth)])
def feed(kind: str = "events", limit: int = 60):
    limit = max(1, min(limit, 300))
    tables = {
        "events": "SELECT ts,kind,text FROM events",
        "journal": "SELECT ts,text,emotion FROM journal",
        "memories": "SELECT ts,text,importance,tags FROM memories",
        "creations": "SELECT id,ts,kind,title,filename,note FROM creations",
        "chat": "SELECT id,ts,sender,text FROM chat",
        "dreams": "SELECT d.id,d.ts,d.title,d.story,d.symbols,d.feeling,d.longing,d.strangeness,c.filename "
                  "FROM dreams d LEFT JOIN creations c ON c.id=d.creation_id",
    }
    if kind not in tables:
        raise HTTPException(404)
    rows = db.q(tables[kind] + (" ORDER BY d.ts" if kind == "dreams" else " ORDER BY ts") + " DESC LIMIT ?", (limit,))
    return list(reversed(rows)) if kind == "chat" else rows


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@app.post("/api/chat", dependencies=[Depends(auth)])
async def chat(msg: ChatIn):
    reply = await asyncio.to_thread(brain.chat, msg.text.strip())
    return {"reply": reply}


class GiftIn(BaseModel):
    food: str


@app.post("/api/gift", dependencies=[Depends(auth)])
def gift(g: GiftIn):
    food = g.food.lower().strip()
    if food not in vitals.FOODS:
        raise HTTPException(400, "Gino doesn't know that food.")
    with brain.mind_lock:
        body = vitals.load()
        body["pantry"][food] = body["pantry"].get(food, 0) + 1
        body["social"] = vitals.clamp(body["social"] + 3)
        vitals.save(body)
    db.event("gift", f"Dad left a {food} in the pantry.")
    return {"ok": True}


@app.post("/api/pet", dependencies=[Depends(auth)])
def pet():
    """Dad petted Gino in the 3D world."""
    now = time.time()
    with brain.mind_lock:
        body = vitals.load()
        if now - body.get("last_pet", 0) > 600:  # a pet only "counts" every 10 minutes
            body["social"] = vitals.clamp(body["social"] + 4)
            body["last_pet"] = now
            vitals.save(body)
            db.event("pet", "Dad petted Gino. He did a happy little hop.")
    return {"ok": True}


@app.post("/api/nudge", dependencies=[Depends(auth)])
def nudge():
    """Let Gino take a turn now (handy for testing)."""
    body = vitals.load()
    body["next_wake"] = 0
    body["asleep_until"] = 0
    vitals.save(body)
    return {"ok": True}


@app.get("/creations/{filename}", dependencies=[Depends(auth)])
def creation(filename: str):
    if not re.fullmatch(r"[a-z0-9\-]+\.(svg|md|txt)", filename):
        raise HTTPException(404)
    path = config.DATA_DIR / "creations" / filename
    if not path.exists():
        raise HTTPException(404)
    if filename.endswith(".svg"):
        return FileResponse(path, media_type="image/svg+xml",
                            headers={"Content-Security-Policy": "script-src 'none'"})
    return PlainTextResponse(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- videos (clips) and TikTok

@app.get("/api/clips", dependencies=[Depends(auth)])
def clip_list():
    return {"on": clips.available(), "clips": clips.listing(), "kinds": clips.KIND_NAMES, "tiktok": tiktok.status()}


class ClipIn(BaseModel):
    kind: str = ""


@app.post("/api/clips", dependencies=[Depends(auth)])
def clip_make(c: ClipIn):
    try:
        return {"id": clips.make(c.kind, by="dad")}
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None


@app.get("/clips/{cid}.mp4", dependencies=[Depends(auth)])
def clip_video(cid: int, download: int = 0, raw: int = 0):
    path = clips.path(cid, raw=bool(raw))
    if not path:
        raise HTTPException(404)
    return FileResponse(path, media_type="video/mp4", filename=path.name if download else None,
                        content_disposition_type="attachment" if download else "inline")


@app.get("/api/clips/polish", dependencies=[Depends(auth)])
def clip_polish_queue():
    """Dad's PC asks which clips it should polish in FilmCraft."""
    return {"clips": clips.polish_queue()}


@app.put("/api/clips/{cid}/polished", dependencies=[Depends(auth)])
async def clip_polished(cid: int, request: Request, failed: int = 0):
    """Dad's PC sends back the polished video (or, with failed=1, a short note saying why it couldn't)."""
    size = int(request.headers.get("content-length") or 0)
    if size > clips.MAX_POLISHED:
        raise HTTPException(413, "That video is too big.")
    data = await request.body()
    if failed:
        clips.polish_failed(cid, data[:300].decode(errors="replace"))
        return {"message": "Noted. Gino will use the original."}
    try:
        return {"message": await asyncio.to_thread(clips.save_polished, cid, data)}
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None


@app.get("/api/tiktok/connect", dependencies=[Depends(auth)])
def tiktok_connect():
    try:
        return {"url": tiktok.connect_url()}
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None


@app.get("/tiktok/callback", response_class=HTMLResponse)
def tiktok_callback(code: str = "", state: str = "", error: str = ""):
    """TikTok sends dad back here after he says yes. The one-time 'state' proves he started it from his page."""
    import html as _h
    if error or not code:
        msg = "TikTok wasn't connected (you pressed cancel, or TikTok said no). You can try again from your page."
    else:
        try:
            name = tiktok.finish_connect(code, state)
            msg = f"🎉 TikTok is connected{(' as ' + name) if name else ''}! You can close this and go back to Gino."
        except RuntimeError as e:
            msg = str(e)
    return HTMLResponse(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                        f"<title>Gino and TikTok</title><body style='font:18px system-ui;max-width:520px;margin:15vh auto;"
                        f"padding:0 16px;text-align:center'><p>{_h.escape(msg)}</p><p><a href='/private'>Back to Gino</a></p>",
                        headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})


@app.post("/api/tiktok/disconnect", dependencies=[Depends(auth)])
def tiktok_disconnect():
    tiktok.disconnect()
    return {"ok": True}


@app.get("/api/tiktok/creator", dependencies=[Depends(auth)])
def tiktok_creator():
    try:
        return tiktok.creator()
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None


class TikTokIn(BaseModel):
    title: str = Field(default="", max_length=2200)
    privacy: str = ""
    allow_comment: bool = False
    allow_duet: bool = False
    allow_stitch: bool = False
    consent: bool = False


@app.post("/api/clips/{cid}/tiktok", dependencies=[Depends(auth)])
def clip_to_tiktok(cid: int, t: TikTokIn):
    if not t.consent:
        raise HTTPException(400, "Please agree to TikTok's terms first.")
    try:
        return {"message": tiktok.send(cid, t.title, t.privacy, t.allow_comment, t.allow_duet, t.allow_stitch)}
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None
