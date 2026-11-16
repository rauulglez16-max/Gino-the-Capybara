"""Gino on WhatsApp, through Meta's official WhatsApp Cloud API. Only ever talks to dad's number.

How WhatsApp's rules shape this:
- Gino may send normal messages only within 24 hours of dad's last message (the "customer service window").
- Outside that window he may only send a pre-approved template. So when he wants to say something then, his
  message waits in a little queue, and he sends one short template nudge ("Gino has a message for you").
  As soon as dad replies, the window is open again and the waiting messages are delivered.

Incoming messages arrive at /whatsapp/webhook. Every request must carry Meta's signature (an HMAC of the body
made with the app secret), and only messages from WHATSAPP_TO are listened to. Everyone else gets silence.
"""
import collections
import hashlib
import hmac
import json
import logging
import threading
import time
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from . import config, db

log = logging.getLogger("gino.whatsapp")
router = APIRouter()

WINDOW = 23.5 * 3600  # Meta's window is 24h; keep a safety margin
MAX_LEN = 4000  # WhatsApp allows 4096 characters per text
MAX_QUEUE = 20
REENGAGE_ERRORS = {131047, 131026}  # "more than 24 hours", "can't deliver": fall back to a nudge

_seen = collections.deque(maxlen=500)  # incoming message ids already handled (Meta retries webhooks)
_sent = collections.OrderedDict()  # our recent message id -> text, to re-queue if delivery fails
_lock = threading.Lock()


def enabled() -> bool:
    return bool(config.WHATSAPP_TOKEN and config.WHATSAPP_PHONE_ID and config.WHATSAPP_TO)


class WhatsAppError(Exception):
    def __init__(self, msg: str, code: int | None = None):
        super().__init__(msg)
        self.code = code


def api(payload: dict, timeout: float = 15) -> dict:
    url = f"{config.WHATSAPP_API}/{config.WHATSAPP_PHONE_ID}/messages"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {config.WHATSAPP_TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode()).get("error", {})
        except Exception:
            err = {}
        raise WhatsAppError(f"HTTP {e.code} {err.get('message', '')}".strip(), err.get("code")) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise WhatsAppError(f"network problem ({type(e).__name__})") from None


# ---------------------------------------------------------------- the 24-hour window

def window_open() -> bool:
    return time.time() - float(db.get("wa_last_in", 0) or 0) < WINDOW


def _send_text(text: str) -> None:
    for i in range(0, len(text), MAX_LEN):
        part = text[i:i + MAX_LEN]
        out = api({"messaging_product": "whatsapp", "to": config.WHATSAPP_TO, "type": "text",
                   "text": {"body": part, "preview_url": True}})
        for m in out.get("messages", []):
            with _lock:
                _sent[m.get("id")] = part
                while len(_sent) > 50:
                    _sent.popitem(last=False)


def _queue(text: str) -> None:
    with _lock:
        q = db.get("wa_queue", []) or []
        q.append(text)
        db.put("wa_queue", q[-MAX_QUEUE:])


def _nudge() -> bool:
    """Send the template nudge, once per closed window."""
    if db.get("wa_nudged", False):
        return True
    try:
        api({"messaging_product": "whatsapp", "to": config.WHATSAPP_TO, "type": "template",
             "template": {"name": config.WHATSAPP_TEMPLATE, "language": {"code": config.WHATSAPP_TEMPLATE_LANG}}})
        db.put("wa_nudged", True)
        db.event("chat", "WhatsApp: Gino sent dad a nudge (his messages wait until dad replies).")
        return True
    except WhatsAppError as e:
        log.warning("Couldn't send the WhatsApp nudge: %s", e)
        return False


def send(text: str) -> str:
    """Send a message to dad's WhatsApp. Returns "sent", "waiting" (queued behind a nudge) or "" on failure.
    Never raises."""
    if not enabled():
        return ""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        if window_open():
            try:
                _send_text(text)
                return "sent"
            except WhatsAppError as e:
                if e.code not in REENGAGE_ERRORS:
                    raise
                db.put("wa_last_in", 0)  # Meta says the window is closed after all
        _queue(text)
        return "waiting" if _nudge() else ""
    except Exception as e:
        log.warning("Couldn't send to WhatsApp: %s", e)
        return ""


def _flush_queue() -> None:
    with _lock:
        q = db.get("wa_queue", []) or []
        db.put("wa_queue", [])
    for i, text in enumerate(q):
        try:
            _send_text(text)
        except WhatsAppError as e:
            log.warning("Couldn't deliver a waiting WhatsApp message: %s", e)
            for rest in q[i:]:
                _queue(rest)
            return


# ---------------------------------------------------------------- incoming

def _read_and_type(msg_id: str) -> None:
    try:
        api({"messaging_product": "whatsapp", "status": "read", "message_id": msg_id,
             "typing_indicator": {"type": "text"}}, timeout=5)
    except Exception:
        pass


def _is_dad(number: str) -> bool:
    return bool(number) and hmac.compare_digest(str(number), str(config.WHATSAPP_TO))


def handle_message(msg: dict) -> None:
    mid = msg.get("id", "")
    with _lock:
        if mid in _seen:
            return
        _seen.append(mid)
    if not _is_dad(msg.get("from", "")):
        log.info("Ignored a WhatsApp message from a number that isn't dad's.")
        return
    db.put("wa_last_in", time.time())
    db.put("wa_nudged", False)
    _read_and_type(mid)
    _flush_queue()  # anything Gino wanted to say while the window was closed
    kind = msg.get("type")
    text = ((msg.get("text") or {}).get("body") or "").strip() if kind == "text" else ""
    if kind == "button":
        text = ((msg.get("button") or {}).get("text") or "").strip()
    if not text:
        _send_text("I can only read words for now, dad 🙈 (no pictures or voice notes yet).")
        return
    from . import brain
    reply = brain.chat(text[:4000])
    _send_text(reply)


def handle_status(st: dict) -> None:
    """Meta tells us when one of our messages failed. If it was because the window closed, re-queue + nudge."""
    if st.get("status") != "failed" or not _is_dad(st.get("recipient_id", "")):
        return
    codes = {e.get("code") for e in st.get("errors", [])}
    with _lock:
        text = _sent.pop(st.get("id"), None)
    log.warning("A WhatsApp message to dad failed (codes %s).", codes)
    if codes & REENGAGE_ERRORS:
        db.put("wa_last_in", 0)
        if text:
            _queue(text)
        _nudge()


def process(payload: dict) -> None:
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            meta = value.get("metadata") or {}
            if str(meta.get("phone_number_id", "")) != str(config.WHATSAPP_PHONE_ID):
                continue  # not Gino's number
            for st in value.get("statuses", []):
                try:
                    handle_status(st)
                except Exception:
                    log.exception("WhatsApp status handling failed")
            for msg in value.get("messages", []):
                try:
                    handle_message(msg)
                except Exception:
                    log.exception("Gino couldn't answer a WhatsApp message")
                    try:
                        _send_text("*blinks* Sorry dad, I got confused for a moment. Can you say that again?")
                    except Exception:
                        pass


def valid_signature(body: bytes, header: str) -> bool:
    if not config.WHATSAPP_APP_SECRET or not header.startswith("sha256="):
        return False
    expected = hmac.new(config.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])


@router.get("/whatsapp/webhook", response_class=PlainTextResponse)
def verify(request: Request):
    """Meta checks the webhook address once, when dad saves it in the Meta dashboard."""
    p = request.query_params
    token = config.WHATSAPP_VERIFY_TOKEN
    if p.get("hub.mode") == "subscribe" and token and hmac.compare_digest(p.get("hub.verify_token", ""), token):
        return p.get("hub.challenge", "")
    raise HTTPException(403)


@router.post("/whatsapp/webhook")
async def incoming(request: Request):
    body = await request.body()
    if not enabled() or not valid_signature(body, request.headers.get("x-hub-signature-256", "")):
        raise HTTPException(403)
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(400) from None
    # Answer Meta right away (it retries slow webhooks); Gino thinks in the background.
    threading.Thread(target=process, args=(payload,), daemon=True).start()
    return {"ok": True}
