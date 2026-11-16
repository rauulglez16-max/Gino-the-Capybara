"""Gino's phone line: a Telegram bot that only ever talks to dad.

Dad's messages reach Gino like a chat on his page, Gino's replies go back to dad's phone, and when Gino
messages dad on his own (message_dad) it pops up on the phone too.

Locked to one chat: the bot only answers the chat id in TELEGRAM_CHAT_ID. Messages from anyone else are
ignored without a reply, so strangers who find the bot get silence. Pairing (finding dad's chat id) is done
once by `gino telegram` on the server, never automatically by the running app.
"""
import json
import logging
import threading
import time
import urllib.error
import urllib.request

from . import config

log = logging.getLogger("gino.telegram")
MAX_LEN = 4000  # Telegram allows 4096 characters per message


def enabled() -> bool:
    return bool(config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID)


class TelegramError(Exception):
    pass


def api(method: str, payload: dict | None = None, timeout: float = 15) -> dict:
    """Call the Telegram Bot API. Errors never include the token (it's in the URL)."""
    url = f"{config.TELEGRAM_API}/bot{config.TELEGRAM_TOKEN}/{method}"
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            desc = json.loads(e.read().decode()).get("description", "")
        except Exception:
            desc = ""
        raise TelegramError(f"{method}: HTTP {e.code} {desc}".strip()) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise TelegramError(f"{method}: network problem ({type(e).__name__})") from None
    if not out.get("ok"):
        raise TelegramError(f"{method}: {out.get('description', 'failed')}")
    return out.get("result")


def _dad_is_asleep() -> bool:
    """Rough night hours for dad, so night-time messages arrive silently."""
    from .brain import local_now
    h = local_now().hour
    return h >= 23 or h < 7


def send(text: str) -> bool:
    """Send a message to dad's phone. Returns True if it got there. Never raises."""
    if not enabled():
        return False
    text = (text or "").strip()
    if not text:
        return False
    try:
        quiet = _dad_is_asleep()
        for i in range(0, len(text), MAX_LEN):
            api("sendMessage", {"chat_id": config.TELEGRAM_CHAT_ID, "text": text[i:i + MAX_LEN],
                                "disable_notification": quiet})
        return True
    except Exception as e:
        log.warning("Couldn't send to Telegram: %s", e)
        return False


def _typing() -> None:
    try:
        api("sendChatAction", {"chat_id": config.TELEGRAM_CHAT_ID, "action": "typing"}, timeout=5)
    except Exception:
        pass


def _is_dad(msg: dict) -> bool:
    chat = msg.get("chat") or {}
    sender = msg.get("from") or {}
    dad = str(config.TELEGRAM_CHAT_ID)
    # Private chat with dad: chat id and sender id are both his user id.
    return chat.get("type") == "private" and str(chat.get("id")) == dad and str(sender.get("id")) == dad


def handle(update: dict) -> None:
    """Deal with one incoming update. Anything not from dad is dropped silently."""
    msg = update.get("message")
    if not msg:
        return  # edits, channel posts, group joins... none of Gino's business
    if not _is_dad(msg):
        chat = msg.get("chat") or {}
        log.info("Ignored a Telegram message from a stranger (chat %s).", chat.get("id"))
        return
    text = (msg.get("text") or "").strip()
    if not text:
        send("I can only read words for now, dad 🙈 (no pictures or voice notes yet).")
        return
    if text in ("/start", "/help"):
        send("Hi dad! 🧡 It's me, Gino. Text me here any time, and I'll message you when I have something to share.")
        return

    from . import brain
    stop = threading.Event()

    def keep_typing():
        while not stop.is_set():
            _typing()
            stop.wait(4.5)

    t = threading.Thread(target=keep_typing, daemon=True)
    t.start()
    try:
        reply = brain.chat(text[:4000])
    finally:
        stop.set()
    send(reply)


def poll_forever(stop: threading.Event) -> None:
    """Long-poll Telegram for dad's messages. Runs in its own thread for as long as Gino is awake."""
    offset = None
    backoff = 5
    log.info("Gino's phone line is on (Telegram).")
    while not stop.is_set():
        try:
            payload = {"timeout": 50, "allowed_updates": ["message"]}
            if offset is not None:
                payload["offset"] = offset
            updates = api("getUpdates", payload, timeout=60) or []
            backoff = 5
        except TelegramError as e:
            log.warning("Telegram: %s. Trying again in %ss.", e, backoff)
            stop.wait(backoff)
            backoff = min(backoff * 2, 300)
            continue
        for u in updates:
            offset = u["update_id"] + 1  # confirm first, so a crash never makes Gino answer twice
            try:
                handle(u)
            except Exception:
                log.exception("Gino couldn't answer a Telegram message")
                send("*blinks* Sorry dad, I got confused for a moment. Can you say that again?")


def start() -> threading.Event | None:
    """Start the phone line in the background if it's set up. Returns an Event that stops it."""
    if not enabled():
        return None
    stop = threading.Event()
    threading.Thread(target=poll_forever, args=(stop,), name="telegram", daemon=True).start()
    return stop
