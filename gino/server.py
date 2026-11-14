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

from . import brain, config, db, vitals

log = logging.getLogger("gino")
STATIC = config.ROOT / "gino" / "static"


async def life_loop():
    """Gino's heartbeat: keeps his body ticking and gives him turns when he wants them."""
    await asyncio.sleep(2)
    while True:
        try:
            if not brain.mind_lock.locked():
                body = vitals.tick(vitals.load())
                vitals.save(body)
                now = time.time()
                if not vitals.is_asleep(body, now) and now >= body.get("next_wake", 0):
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
    mode = "practice brain (no API key)" if config.FAKE_BRAIN else config.MODEL
    log.info("Gino is awake. Brain: %s. Daily budget: $%.2f", mode, config.DAILY_BUDGET_USD)
    task = asyncio.create_task(life_loop())
    yield
    task.cancel()


app = FastAPI(title="Gino", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def auth(request: Request):
    if not config.PASSWORD:
        return
    given = request.headers.get("x-gino-key") or request.query_params.get("key") or ""
    if not secrets.compare_digest(given, config.PASSWORD):
        raise HTTPException(401, "Gino doesn't know you.")


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/state", dependencies=[Depends(auth)])
def state():
    body = vitals.load()
    now = time.time()
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
        "habitat": db.q("SELECT id,name,emoji,x,y,description,kind,color,size FROM habitat ORDER BY id"),
        "goals": db.q("SELECT id,title,why,steps,progress,status FROM goals ORDER BY status='active' DESC, updated DESC LIMIT 30"),
        "brain": "practice" if config.FAKE_BRAIN else config.MODEL,
        "spent_today": round(brain.spent_today(), 3), "budget": config.DAILY_BUDGET_USD,
        "foods": {k: v[2] for k, v in vitals.FOODS.items()},
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
    }
    if kind not in tables:
        raise HTTPException(404)
    rows = db.q(tables[kind] + " ORDER BY ts DESC LIMIT ?", (limit,))
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
