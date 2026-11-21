"""Sending Gino's clips to TikTok, through TikTok's official Content Posting API. Off unless dad sets it up.

Two ways, chosen with GINO_TIKTOK_MODE:
  drafts (default)  the clip lands in the inbox of dad's TikTok app as a draft. He opens it, ticks TikTok's
                    "AI-generated content" label, and posts it. Needs the video.upload permission, which is the
                    easiest one to get from TikTok.
  direct            the clip goes straight onto the account. Needs the video.publish permission. Until TikTok has
                    reviewed ("audited") dad's developer app, TikTok only allows these posts to be private (only
                    the account owner can see them) on a private account. Every direct post is labelled
                    AI-generated (is_aigc).

TikTok's rules say a person has to choose who can see each post and agree to TikTok's music terms, so by default
dad presses "Send to TikTok" on his private page. GINO_TIKTOK_AUTO=1 sends each new daily clip by itself; that is
a good fit for drafts mode (dad still finishes the post in the app). Nothing on TikTok can talk back to Gino: this
code only uploads videos. The keys and tokens stay on the server and never reach any page.

TikTok's docs: https://developers.tiktok.com/doc/content-posting-api-get-started
"""
import json
import logging
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import clips, config, db, public

log = logging.getLogger("gino.tiktok")
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
PRIVACY = {"PUBLIC_TO_EVERYONE": "Everyone", "MUTUAL_FOLLOW_FRIENDS": "Friends",
           "FOLLOWER_OF_CREATOR": "Followers", "SELF_ONLY": "Only me"}
MAX_TITLE = 2200
_send_lock = threading.Lock()


def mode() -> str:
    return "direct" if config.TIKTOK_MODE == "direct" else "drafts"


def configured() -> bool:
    return bool(config.TIKTOK_CLIENT_KEY and config.TIKTOK_CLIENT_SECRET)


def redirect_uri() -> str:
    return f"{(config.PUBLIC_URL or '').rstrip('/')}/tiktok/callback"


def _auth() -> dict:
    return db.get("tiktok_auth", {}) or {}


def connected() -> bool:
    a = _auth()
    return configured() and bool(a.get("refresh_token")) and a.get("refresh_expires", 0) > time.time()


def status() -> dict:
    a = _auth()
    return {"configured": configured(), "connected": connected(), "mode": mode(), "auto": config.TIKTOK_AUTO,
            "name": a.get("name", ""), "redirect_uri": redirect_uri() if config.PUBLIC_URL else ""}


# ---------------------------------------------------------------- talking to TikTok

def _http(url: str, data: bytes | None = None, headers: dict | None = None, method: str = "POST",
          timeout: int = 30) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": "gino-capybara",
                                                                          **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw.strip().startswith(b"{") else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {}


def _error(body: dict) -> str:
    err = body.get("error") or {}
    if isinstance(err, dict) and err.get("code") not in (None, "", "ok"):
        return f"{err.get('code')}: {err.get('message', '')}".strip(": ")
    if body.get("error_description"):
        return str(body["error_description"])
    return ""


def _api(path: str, body: dict | None = None) -> dict:
    code, r = _http(f"{config.TIKTOK_API}{path}", json.dumps(body or {}).encode(),
                    {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json; charset=UTF-8"})
    problem = _error(r)
    if code >= 400 or problem:
        raise RuntimeError(_friendly(problem or f"TikTok said {code}"))
    return r.get("data") or {}


def _friendly(problem: str) -> str:
    hints = {
        "unaudited_client_can_only_post_to_private_accounts":
            "TikTok only lets apps it hasn't reviewed post to PRIVATE accounts. Make the TikTok account private, "
            "or use drafts mode (gino tiktok mode drafts).",
        "spam_risk_too_many_pending_share": "TikTok's inbox already has 5 drafts waiting. Post or delete some first.",
        "spam_risk_too_many_posts": "TikTok says that's enough posts for today. Try again tomorrow.",
        "privacy_level_option_mismatch": "That 'who can see it' choice isn't allowed for this account.",
        "access_token_invalid": "The TikTok connection has expired. Connect again from the private page.",
        "scope_not_authorized": "The TikTok connection doesn't have permission for this. Connect again.",
    }
    for k, v in hints.items():
        if k in problem:
            return v
    return f"TikTok said: {problem}"


def _save_tokens(r: dict) -> None:
    now = time.time()
    old = _auth()
    db.put("tiktok_auth", {**old, "access_token": r["access_token"], "expires": now + int(r.get("expires_in", 0)) - 120,
                           "refresh_token": r.get("refresh_token", old.get("refresh_token", "")),
                           "refresh_expires": now + int(r.get("refresh_expires_in", 0) or 0),
                           "open_id": r.get("open_id", old.get("open_id", "")), "scope": r.get("scope", "")})


def _token() -> str:
    a = _auth()
    if a.get("access_token") and a.get("expires", 0) > time.time():
        return a["access_token"]
    if not a.get("refresh_token"):
        raise RuntimeError("TikTok isn't connected yet. Press 'Connect TikTok' on the private page.")
    # refresh tokens change every time: always keep the newest one
    code, r = _http(f"{config.TIKTOK_API}/v2/oauth/token/", urllib.parse.urlencode({
        "client_key": config.TIKTOK_CLIENT_KEY, "client_secret": config.TIKTOK_CLIENT_SECRET,
        "grant_type": "refresh_token", "refresh_token": a["refresh_token"]}).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"})
    if code >= 400 or not r.get("access_token"):
        raise RuntimeError("The TikTok connection has expired. Press 'Connect TikTok' on the private page again.")
    _save_tokens(r)
    return r["access_token"]


# ---------------------------------------------------------------- connecting dad's account (OAuth)

def connect_url() -> str:
    if not configured():
        raise RuntimeError("TikTok isn't set up on the server yet (gino tiktok setup).")
    if not config.PUBLIC_URL:
        raise RuntimeError("The server doesn't know its own web address yet (gino tiktok setup sets it).")
    state = secrets.token_urlsafe(24)
    db.put("tiktok_state", {"state": state, "ts": time.time()})
    scope = "user.info.basic," + ("video.publish" if mode() == "direct" else "video.upload")
    return AUTH_URL + "?" + urllib.parse.urlencode({
        "client_key": config.TIKTOK_CLIENT_KEY, "scope": scope, "response_type": "code",
        "redirect_uri": redirect_uri(), "state": state})


def finish_connect(code: str, state: str) -> str:
    """TikTok sent dad back here after he said yes. Returns the account's name."""
    want = db.get("tiktok_state", {}) or {}
    if not state or not secrets.compare_digest(str(want.get("state", "")), str(state)) or \
            time.time() - want.get("ts", 0) > 900:
        raise RuntimeError("That link is old or wasn't started from the private page. Press 'Connect TikTok' again.")
    db.put("tiktok_state", {})
    c, r = _http(f"{config.TIKTOK_API}/v2/oauth/token/", urllib.parse.urlencode({
        "client_key": config.TIKTOK_CLIENT_KEY, "client_secret": config.TIKTOK_CLIENT_SECRET, "code": code,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri()}).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"})
    if c >= 400 or not r.get("access_token"):
        raise RuntimeError(_friendly(_error(r) or f"TikTok said {c}"))
    _save_tokens(r)
    name = ""
    try:
        code2, u = _http(f"{config.TIKTOK_API}/v2/user/info/?fields=display_name", None,
                         {"Authorization": f"Bearer {r['access_token']}"}, method="GET")
        name = ((u.get("data") or {}).get("user") or {}).get("display_name", "")
    except Exception:  # noqa: BLE001
        pass
    db.put("tiktok_auth", {**_auth(), "name": name[:80]})
    db.event("tiktok", "dad connected Gino's TikTok account")
    return name


def disconnect() -> None:
    db.put("tiktok_auth", {})


def creator() -> dict:
    """Who's posting and what TikTok allows right now (TikTok asks apps to check this before every post)."""
    d = _api("/v2/post/publish/creator_info/query/")
    return {"nickname": d.get("creator_nickname", ""), "username": d.get("creator_username", ""),
            "privacy": [p for p in d.get("privacy_level_options", []) if p in PRIVACY],
            "privacy_names": PRIVACY, "comment_disabled": bool(d.get("comment_disabled")),
            "duet_disabled": bool(d.get("duet_disabled")), "stitch_disabled": bool(d.get("stitch_disabled")),
            "max_seconds": int(d.get("max_video_post_duration_sec") or 0)}


# ---------------------------------------------------------------- sending a clip

def _mark(cid: int, status: str, note: str = "", publish_id: str | None = None) -> None:
    db.x("UPDATE clips SET tiktok_status=?, tiktok_note=?, tiktok_ts=?" + (", tiktok_id=?" if publish_id else "")
         + " WHERE id=?", (status, note[:300], time.time(), *([publish_id] if publish_id else []), cid))


def send(cid: int, title: str = "", privacy: str = "", allow_comment: bool = False, allow_duet: bool = False,
         allow_stitch: bool = False, by: str = "dad") -> str:
    """Upload one clip. Returns what happened, in plain words. Raises RuntimeError if it can't."""
    if not connected():
        raise RuntimeError("TikTok isn't connected yet.")
    video = clips.path(cid)
    row = db.q("SELECT caption, tiktok_status, seconds FROM clips WHERE id=?", (cid,))
    if not video or not row:
        raise RuntimeError("That clip isn't ready.")
    if row[0]["tiktok_status"] in ("sending", "sent", "posted"):
        raise RuntimeError("That clip has already gone to TikTok.")
    title = " ".join(str(title or row[0]["caption"]).split())[:MAX_TITLE]
    problem = public.check(title)
    if problem:
        raise RuntimeError("The caption mentions something private, so it can't go on TikTok. " + problem)
    size = video.stat().st_size
    if size > 64_000_000:
        raise RuntimeError("That clip is too big to send in one piece.")
    source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}
    with _send_lock:
        _mark(cid, "sending", f"sent by {by}")
        try:
            if mode() == "direct":
                info = creator()
                if privacy not in info["privacy"]:
                    raise RuntimeError("Choose who can see it first.")
                if info["max_seconds"] and row[0]["seconds"] > info["max_seconds"]:
                    raise RuntimeError(f"This account can only post videos up to {info['max_seconds']} seconds.")
                d = _api("/v2/post/publish/video/init/", {
                    "post_info": {"title": title, "privacy_level": privacy, "is_aigc": True,
                                  "disable_comment": info["comment_disabled"] or not allow_comment,
                                  "disable_duet": info["duet_disabled"] or not allow_duet,
                                  "disable_stitch": info["stitch_disabled"] or not allow_stitch,
                                  "video_cover_timestamp_ms": 4000,
                                  "brand_content_toggle": False, "brand_organic_toggle": False},
                    "source_info": source})
            else:
                d = _api("/v2/post/publish/inbox/video/init/", {"source_info": source})
            code, _ = _http(d["upload_url"], video.read_bytes(), {
                "Content-Type": "video/mp4", "Content-Length": str(size),
                "Content-Range": f"bytes 0-{size - 1}/{size}"}, method="PUT", timeout=300)
            if code not in (200, 201):
                raise RuntimeError(f"The upload didn't go through (TikTok said {code}).")
        except Exception as e:
            msg = str(e) if isinstance(e, RuntimeError) else "Couldn't reach TikTok."
            log.warning("TikTok send failed for clip %s: %s", cid, e)
            _mark(cid, "failed", msg)
            raise RuntimeError(msg) from None
    pid = str(d.get("publish_id", ""))
    _mark(cid, "sending", "TikTok is processing it (this can take a few minutes)", pid)
    threading.Thread(target=_watch, args=(cid, pid), daemon=True).start()
    db.event("tiktok", f"sent a clip to TikTok ({mode()})")
    if mode() == "direct":
        return "Sent! TikTok is processing it. It shows up on the account in a few minutes."
    return "Sent! Open the TikTok app: it's waiting in your inbox. Tick 'AI-generated content' and post it."


def _watch(cid: int, pid: str) -> None:
    """Ask TikTok how the upload is doing for up to ~10 minutes."""
    for wait in (10, 20, 30, 60, 60, 120, 120, 180):
        time.sleep(wait)
        try:
            d = _api("/v2/post/publish/status/fetch/", {"publish_id": pid})
        except RuntimeError as e:
            log.info("TikTok status check: %s", e)
            continue
        st = str(d.get("status", ""))
        if st == "PUBLISH_COMPLETE":
            return _mark(cid, "posted", "On TikTok now")
        if st == "SEND_TO_USER_INBOX":
            return _mark(cid, "sent", "Waiting in your TikTok inbox: finish posting it in the app")
        if st == "FAILED":
            return _mark(cid, "failed", f"TikTok couldn't use it ({d.get('fail_reason', 'no reason given')})")
    _mark(cid, "sent", "Sent; TikTok didn't say when it finished. Check the app.")


POLISH_WAIT = 45 * 60  # how long a daily clip waits for its finishing touch before it goes as it is


def after_clip(cid: int) -> None:
    """A new clip is ready. With GINO_TIKTOK_AUTO=1, the daily clips go to TikTok by themselves."""
    if not (config.TIKTOK_AUTO and connected()):
        return
    if not db.q("SELECT 1 FROM clips WHERE id=? AND made_by!='dad'", (cid,)):
        return  # clips dad asks for wait for him to send them
    from . import polish
    if polish.expected(cid):  # FilmCraft or the server will polish it soon: give them a little while first
        threading.Thread(target=_send_when_polished, args=(cid,), daemon=True, name=f"tiktok-wait-{cid}").start()
        return
    _auto_send(cid)


def _send_when_polished(cid: int, wait: float = POLISH_WAIT, step: float = 30) -> None:
    end = time.time() + wait
    while time.time() < end:
        if db.q("SELECT 1 FROM clips WHERE id=? AND (polished!='' OR polish_note!='')", (cid,)):
            break
        time.sleep(step)
    _auto_send(cid)


def _auto_send(cid: int) -> None:
    try:
        privacy = ""
        if mode() == "direct":
            opts = creator()["privacy"]
            wanted = config.TIKTOK_PRIVACY if config.TIKTOK_PRIVACY in opts else "SELF_ONLY"
            if wanted not in opts:
                raise RuntimeError("no allowed privacy setting")
            privacy = wanted
        send(cid, privacy=privacy, by="Gino (automatic)")
    except RuntimeError as e:
        log.info("Automatic TikTok send skipped: %s", e)

