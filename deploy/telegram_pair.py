"""Pair Gino's Telegram bot with dad's phone. Used by `gino telegram`; only needs plain Python.

Reads the bot token from the TELEGRAM_BOT_TOKEN environment variable (never from the command line, so it
doesn't show up in the process list). Talks to the user on stderr and prints only dad's chat id on stdout.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("TELEGRAM_API", "https://api.telegram.org").rstrip("/")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
WAIT_SECONDS = int(os.environ.get("PAIR_WAIT_SECONDS", "300"))


def say(*a):
    print(*a, file=sys.stderr, flush=True)


def api(method, payload=None, timeout=15):
    req = urllib.request.Request(f"{API}/bot{TOKEN}/{method}", data=json.dumps(payload or {}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            out = json.loads(e.read().decode())
        except Exception:
            out = {"ok": False, "description": f"HTTP {e.code}"}
    except (urllib.error.URLError, OSError) as e:
        say(f"Couldn't reach Telegram ({type(e).__name__}). Check the server's internet and try again.")
        sys.exit(1)
    if not out.get("ok"):
        return None, out.get("description", "unknown error")
    return out.get("result"), None


def main():
    if ":" not in TOKEN:
        say("That doesn't look like a bot token. It looks like 123456789:ABCdef... (copy it from BotFather).")
        sys.exit(1)
    me, err = api("getMe")
    if not me:
        say(f"Telegram didn't accept that token ({err}). Copy it again from BotFather and retry.")
        sys.exit(1)
    api("deleteWebhook")  # long polling only works without a webhook
    name = me.get("username", "your bot")
    say(f"\n✅ Found your bot: @{name}")
    say(f"\n👉 Now open Telegram on your phone, search for @{name}, tap Start (or send it \"hi\").")
    say(f"   Waiting for your message (up to {WAIT_SECONDS // 60} minutes)...")

    deadline = time.time() + WAIT_SECONDS
    offset = None
    while time.time() < deadline:
        payload = {"timeout": 25, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        updates, err = api("getUpdates", payload, timeout=35)
        if updates is None:
            if "Conflict" in (err or ""):
                say("   (Gino is still holding the line, waiting a moment...)")
                time.sleep(3)
                continue
            say(f"Telegram said: {err}")
            sys.exit(1)
        for u in updates:
            offset = u["update_id"] + 1
            msg = u.get("message") or {}
            chat = msg.get("chat") or {}
            if chat.get("type") != "private":
                continue
            api("getUpdates", {"offset": offset, "timeout": 0})  # mark it read so Gino doesn't answer "hi" twice
            first = (msg.get("from") or {}).get("first_name", "you")
            say(f"\n📱 Got a message from {first}. That's the only person Gino will ever talk to on Telegram.")
            api("sendMessage", {"chat_id": chat["id"],
                                "text": "📱 Connected! This is Gino's phone line now. He'll text you here, "
                                        "and you can text him back any time. 🧡"})
            print(chat["id"])
            return
    say("\nDidn't hear anything in time. Run `gino telegram` again when your phone is handy.")
    sys.exit(1)


if __name__ == "__main__":
    main()
