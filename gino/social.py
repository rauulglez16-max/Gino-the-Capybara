"""Gino's Bluesky account: he can post short updates about his day. Post only, nothing else.

Safety rules, all enforced here rather than trusted to the model:
- Gino can only create new top-level posts. There is no code to reply, quote, like, follow, DM or read
  mentions, so nobody on Bluesky can talk to him through it.
- Every post goes through the same privacy filter as his public website (public.check), plus a few extra
  rules: no @mentions and no links except to his own website.
- At most GINO_SOCIAL_MAX_PER_DAY posts in any 24 hours, at least GINO_SOCIAL_MIN_GAP_MINUTES apart.
- It's off unless dad switches it on (GINO_SOCIAL=1) and gives it a handle and an app password.
- Every post is saved in the `social_posts` table and shown on his public website.

Uses Bluesky's public HTTP API (https://docs.bsky.app) with the standard library, so no new dependencies.
"""
import json
import logging
import re
import time
import urllib.error
import urllib.request

from . import config, db, public

log = logging.getLogger("gino.social")

MAX_CHARS = 300  # Bluesky's limit is 300 graphemes; counting characters is stricter, so always safe
_MENTION = re.compile(r"(?<![\w/])@[\w.-]+")
_URL = re.compile(r"https?://[^\s<>\"')\]]*[^\s<>\"')\].,!?;:]")


def configured() -> bool:
    return bool(config.SOCIAL_ON and config.BLUESKY_HANDLE and config.BLUESKY_APP_PASSWORD)


def profile_url() -> str:
    return f"https://bsky.app/profile/{config.BLUESKY_HANDLE}" if config.BLUESKY_HANDLE else ""


# ---------------------------------------------------------------- rules

def _recent(seconds: float) -> list[dict]:
    return db.q("SELECT ts FROM social_posts WHERE status='posted' AND ts>? ORDER BY ts DESC",
                (time.time() - seconds,))


def wait_minutes() -> int:
    """0 if Gino may post now, else how many minutes until he can."""
    now = time.time()
    day = _recent(24 * 3600)
    waits = []
    if len(day) >= config.SOCIAL_MAX_PER_DAY:
        waits.append(day[config.SOCIAL_MAX_PER_DAY - 1]["ts"] + 24 * 3600 - now)
    if day and now - day[0]["ts"] < config.SOCIAL_MIN_GAP_MINUTES * 60:
        waits.append(day[0]["ts"] + config.SOCIAL_MIN_GAP_MINUTES * 60 - now)
    return max(0, int(max(waits, default=0) // 60) + (1 if waits else 0))


def problem(text: str) -> str | None:
    """Why this can't go on Bluesky, or None if it's fine."""
    if not text:
        return "The post was empty."
    if len(text) > MAX_CHARS:
        return f"Too long: {len(text)} characters, Bluesky allows {MAX_CHARS}. Make it shorter."
    found = public.check(text)
    if found:
        return found.replace("public website", "Bluesky account")
    if _MENTION.search(text):
        return "No @mentions: you only post about your own day, you don't talk to other accounts."
    home = config.PUBLIC_URL.rstrip("/")
    for url in _URL.findall(text):
        if not home or not (url == home or url.startswith(home + "/")):
            return ("The only links you may post are to your own website"
                    + (f" ({home}/blog)." if home else ", and its address isn't set up, so no links for now."))
    return None


# ---------------------------------------------------------------- Bluesky API

def _call(method: str, body: dict, token: str = "") -> dict:
    req = urllib.request.Request(
        f"{config.BLUESKY_SERVICE.rstrip('/')}/xrpc/{method}", data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "gino-capybara",
                 **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("message", "")
        except Exception:
            msg = ""
        raise RuntimeError(f"Bluesky said {e.code} {msg}".strip()) from None


def _login() -> dict:
    return _call("com.atproto.server.createSession",
                 {"identifier": config.BLUESKY_HANDLE, "password": config.BLUESKY_APP_PASSWORD})


def _facets(text: str) -> list[dict]:
    """Make links clickable. Bluesky wants byte offsets in UTF-8."""
    out = []
    for m in _URL.finditer(text):
        start = len(text[:m.start()].encode())
        out.append({"index": {"byteStart": start, "byteEnd": start + len(m.group(0).encode())},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group(0)}]})
    return out


def _send(text: str) -> str:
    s = _login()
    record = {"$type": "app.bsky.feed.post", "text": text, "langs": ["en"],
              "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())}
    facets = _facets(text)
    if facets:
        record["facets"] = facets
    r = _call("com.atproto.repo.createRecord",
              {"repo": s["did"], "collection": "app.bsky.feed.post", "record": record}, s["accessJwt"])
    return r.get("uri", "")


def web_link(uri: str) -> str:
    """at://did/app.bsky.feed.post/rkey -> https://bsky.app/profile/did/post/rkey"""
    m = re.fullmatch(r"at://([^/]+)/app\.bsky\.feed\.post/([\w~.:-]+)", uri or "")
    return f"https://bsky.app/profile/{m.group(1)}/post/{m.group(2)}" if m else ""


# ---------------------------------------------------------------- what Gino calls

def post(text: str) -> str:
    text = str(text or "").strip()
    if not configured():
        return "You don't have a Bluesky account switched on right now."
    why = problem(text)
    if why:
        return "Not posted. " + why
    wait = wait_minutes()
    if wait:
        return (f"Not posted: you can post at most {config.SOCIAL_MAX_PER_DAY} times a day, at least "
                f"{config.SOCIAL_MIN_GAP_MINUTES} minutes apart. You can post again in about {wait} minutes.")
    try:
        uri = _send(text)
    except Exception as e:  # network trouble or Bluesky refusing: tell Gino, never crash his turn
        log.warning("Bluesky post failed: %s", e)
        db.x("INSERT INTO social_posts(ts,text,uri,status) VALUES(?,?,?,?)", (time.time(), text, "", "failed"))
        return "Bluesky didn't take the post (maybe it's down). Try again another time."
    db.x("INSERT INTO social_posts(ts,text,uri,status) VALUES(?,?,?,?)", (time.time(), text, uri, "posted"))
    db.event("social", "posted on Bluesky: " + text[:120])
    return "Posted on Bluesky! 🦋"


def context_lines() -> str:
    """What Gino sees about his Bluesky account each turn."""
    if not configured():
        return ""
    last = db.q("SELECT ts,text FROM social_posts WHERE status='posted' ORDER BY ts DESC LIMIT 3")
    wait = wait_minutes()
    lines = [f"\n## Your Bluesky account (@{config.BLUESKY_HANDLE}, public)",
             "You can post now with social_post." if not wait else f"You can post again in about {wait} minutes."]
    if last:
        lines.append("Your latest posts: " + " | ".join(
            f"({time.strftime('%d %b %H:%M', time.localtime(p['ts']))}) {p['text'][:140]}" for p in last))
    return "\n".join(lines)


def recent_public(n: int = 5) -> list[dict]:
    return db.q("SELECT ts,text,uri FROM social_posts WHERE status='posted' ORDER BY ts DESC LIMIT ?", (n,))


if __name__ == "__main__":  # `python -m gino.social test` checks the login without posting anything
    import sys
    if sys.argv[1:] == ["test"]:
        if not (config.BLUESKY_HANDLE and config.BLUESKY_APP_PASSWORD):
            sys.exit("No Bluesky handle or app password set.")
        try:
            print(f"Logged in to Bluesky as @{_login().get('handle', config.BLUESKY_HANDLE)}. Nothing was posted.")
        except Exception as e:
            sys.exit(f"Couldn't log in: {e}")
    else:
        print("usage: python -m gino.social test")
