"""Gino's shop: he sells his own drawings as digital downloads, and dad gets the money.

How it works:
- Gino picks one of his drawings, names it, describes it and sets a price (within dad's limits). His server
  creates the product in dad's Stripe account. Gino never sees or touches any key: it lives in the server's
  settings and only this file uses it.
- The shop page (/blog/shop) shows what's for sale. "Buy" sends the buyer to a Stripe checkout with Managed
  Payments switched on, so Stripe is the official seller: it handles VAT everywhere, fraud, receipts and buyer
  questions. The money lands in dad's Stripe balance and is paid out to his bank automatically.
- After paying, Stripe sends the buyer back to /shop/thanks, where the server checks with Stripe that the
  payment really went through and hands over the file. Gino hears that something sold, never who bought it.

Safety rules, all enforced here rather than trusted to the model:
- The Stripe key should be a RESTRICTED key that can only write Products, Prices and Checkout Sessions. It can't
  refund, pay out, move money or read card details. There is no code here for refunds, payouts, or messaging buyers.
- Prices must sit between GINO_SHOP_MIN_PRICE and GINO_SHOP_MAX_PRICE (default £1 to £10).
- At most GINO_SHOP_MAX_NEW_PER_DAY new listings a day and GINO_SHOP_MAX_ITEMS for sale at once.
- Everything goes through the same privacy filter as his public website (public.check).
- Every item says clearly it was made by an AI capybara.
- It's off unless dad switches it on (GINO_SHOP=1) with a key. `gino shop off` closes it at once.

Uses Stripe's HTTP API with the standard library, so no new dependencies.
"""
import html
import json
import logging
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from . import config, db, public

log = logging.getLogger("gino.shop")
router = APIRouter()
E = html.escape

STRIPE_API = "https://api.stripe.com/v1"
STRIPE_VERSION = "2025-03-31.basil"  # Managed Payments needs this version or later
TAX_CODE_ART = "txcd_10505001"  # "Digital Finished Artwork - downloaded - with permanent rights" (Managed Payments eligible)
MAX_DOWNLOADS = 10  # per purchase
DOWNLOAD_DAYS = 30
AI_LABEL = "Made by Gino, an AI capybara. No human drew this."

SCHEMA = """
CREATE TABLE IF NOT EXISTS shop_items (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, updated REAL NOT NULL,
  creation_id INTEGER NOT NULL REFERENCES creations(id), title TEXT NOT NULL, description TEXT NOT NULL,
  price_pence INTEGER NOT NULL CHECK (price_pence > 0),
  status TEXT NOT NULL DEFAULT 'listed' CHECK (status IN ('listed','unlisted')),
  stripe_product TEXT NOT NULL DEFAULT '', stripe_price TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS shop_sales (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, item_id INTEGER NOT NULL REFERENCES shop_items(id),
  session_id TEXT NOT NULL UNIQUE, amount_pence INTEGER NOT NULL, currency TEXT NOT NULL,
  downloads INTEGER NOT NULL DEFAULT 0, told_gino INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS shop_items_status ON shop_items(status);
"""

_schema_ready = False
_buy_lock = threading.Lock()
_buy_times: dict[str, list[float]] = {}


def _db() -> None:
    global _schema_ready
    if not _schema_ready:
        db.conn().executescript(SCHEMA)
        _schema_ready = True


def configured() -> bool:
    return bool(config.SHOP_ON and config.STRIPE_KEY and config.PUBLIC_URL)


def _money(pence: int) -> str:
    return f"£{pence / 100:.2f}"


def _pence(price) -> int | None:
    try:
        return int(round(float(str(price).replace("£", "").strip()) * 100))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- Stripe

class StripeError(RuntimeError):
    pass


def _flat(params: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Stripe wants nested form fields: line_items[0][price]=..."""
    out = []
    for k, v in params.items():
        key = f"{prefix}[{k}]" if prefix else str(k)
        if isinstance(v, dict):
            out += _flat(v, key)
        elif isinstance(v, list):
            for i, item in enumerate(v):
                out += _flat(item, f"{key}[{i}]") if isinstance(item, dict) else [(f"{key}[{i}]", str(item))]
        elif isinstance(v, bool):
            out.append((key, "true" if v else "false"))
        elif v is not None:
            out.append((key, str(v)))
    return out


def stripe(method: str, path: str, params: dict | None = None, idem: str = "") -> dict:
    data = urllib.parse.urlencode(_flat(params or {})).encode() if method == "POST" else None
    url = STRIPE_API + path
    if method == "GET" and params:
        url += "?" + urllib.parse.urlencode(_flat(params))
    headers = {"Authorization": f"Bearer {config.STRIPE_KEY}", "Stripe-Version": STRIPE_VERSION,
               "User-Agent": "gino-capybara"}
    if idem:
        headers["Idempotency-Key"] = idem
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise StripeError(f"Stripe said {e.code}: {msg}".strip()) from None
    except urllib.error.URLError as e:
        raise StripeError(f"couldn't reach Stripe ({e.reason})") from None


# ---------------------------------------------------------------- rules

def _creation(cid) -> dict | None:
    try:
        rows = db.q("SELECT id,kind,title,filename FROM creations WHERE id=?", (int(cid),))
    except (TypeError, ValueError):
        return None
    return rows[0] if rows else None


def _price_problem(pence: int | None) -> str | None:
    lo, hi = config.SHOP_MIN_PENCE, config.SHOP_MAX_PENCE
    if pence is None or not lo <= pence <= hi:
        return f"Prices must be between {_money(lo)} and {_money(hi)}."
    return None


def _listed_today() -> int:
    return db.q("SELECT COUNT(*) AS n FROM shop_items WHERE ts>?", (time.time() - 24 * 3600,))[0]["n"]


def _item(item_id) -> dict | None:
    _db()
    try:
        rows = db.q("SELECT * FROM shop_items WHERE id=?", (int(item_id),))
    except (TypeError, ValueError):
        return None
    return rows[0] if rows else None


def _product_text(description: str) -> str:
    return f"{description}\n\n{AI_LABEL} Digital download (SVG): it opens in any web browser and prints sharp at any size."


# ---------------------------------------------------------------- what Gino calls

def list_item(creation_id, title: str, description: str, price) -> str:
    _db()
    if not configured():
        return "Your shop isn't open right now."
    title, description = " ".join(str(title or "").split())[:80], str(description or "").strip()[:600]
    c = _creation(creation_id)
    if not c:
        return f"You don't have a creation #{creation_id}."
    if c["kind"] != "svg":
        return "For now your shop sells drawings only. Pick one of your drawings (an svg creation)."
    if not (config.DATA_DIR / "creations" / c["filename"]).exists():
        return "That drawing's file is missing, so it can't be sold."
    if len(title) < 2 or len(description) < 10:
        return "Give it a proper name and a short description (a sentence or two) so buyers know what it is."
    pence = _pence(price)
    why = _price_problem(pence) or public.check(title, description, public.creation_text(c))  # the drawing too
    if why:
        return "Not listed. " + why.replace("public website", "shop")
    if db.q("SELECT 1 FROM shop_items WHERE creation_id=? AND status='listed'", (c["id"],)):
        return "That drawing is already in your shop. Use shop_update to change it."
    if db.q("SELECT COUNT(*) AS n FROM shop_items WHERE status='listed'")[0]["n"] >= config.SHOP_MAX_ITEMS:
        return f"Your shop is full ({config.SHOP_MAX_ITEMS} things). Take something down first with shop_unlist."
    if _listed_today() >= config.SHOP_MAX_NEW_PER_DAY:
        return (f"You can add at most {config.SHOP_MAX_NEW_PER_DAY} new things a day. "
                "Save this one for tomorrow.")
    now = time.time()
    iid = db.x("INSERT INTO shop_items(ts,updated,creation_id,title,description,price_pence,status) "
               "VALUES(?,?,?,?,?,?,'unlisted')", (now, now, c["id"], title, description, pence))
    try:
        prod = stripe("POST", "/products", {
            "name": title, "description": _product_text(description), "tax_code": TAX_CODE_ART,
            "metadata": {"gino_item": iid},
            "default_price_data": {"currency": "gbp", "unit_amount": pence}}, idem=f"gino-item-{iid}")
    except StripeError as e:
        log.warning("Couldn't create Stripe product: %s", e)
        db.x("DELETE FROM shop_items WHERE id=?", (iid,))
        return f"The shop's till isn't working right now ({e}). Try again later."
    db.x("UPDATE shop_items SET status='listed', stripe_product=?, stripe_price=? WHERE id=?",
         (prod.get("id", ""), prod.get("default_price") or "", iid))
    db.event("shop", f"put '{title}' up for sale in his shop at {_money(pence)}")
    return f"'{title}' is for sale in your shop at {_money(pence)} (item #{iid}). Anyone can buy it at /blog/shop."


def update_item(item_id, price=None, title: str = "", description: str = "") -> str:
    it = _item(item_id)
    if not it or it["status"] != "listed":
        return f"There's no item #{item_id} for sale in your shop."
    title = " ".join(str(title or "").split())[:80] or it["title"]
    description = str(description or "").strip()[:600] or it["description"]
    pence = _pence(price) if price not in (None, "") else it["price_pence"]
    c = _creation(it["creation_id"])
    why = _price_problem(pence) or public.check(title, description, public.creation_text(c) if c else "")
    if why:
        return "Not changed. " + why.replace("public website", "shop")
    try:
        new_price = it["stripe_price"]
        if pence != it["price_pence"]:
            new_price = stripe("POST", "/prices", {"product": it["stripe_product"], "currency": "gbp",
                                                   "unit_amount": pence})["id"]
        stripe("POST", f"/products/{it['stripe_product']}", {
            "name": title, "description": _product_text(description), "default_price": new_price})
    except (StripeError, KeyError) as e:
        return f"The shop's till isn't working right now ({e}). Try again later."
    db.x("UPDATE shop_items SET title=?, description=?, price_pence=?, stripe_price=?, updated=? WHERE id=?",
         (title, description, pence, new_price, time.time(), it["id"]))
    db.event("shop", f"updated '{title}' in his shop ({_money(pence)})")
    return f"Updated item #{it['id']}: '{title}' at {_money(pence)}."


def unlist(item_id) -> str:
    it = _item(item_id)
    if not it or it["status"] != "listed":
        return f"There's no item #{item_id} for sale in your shop."
    db.x("UPDATE shop_items SET status='unlisted', updated=? WHERE id=?", (time.time(), it["id"]))
    try:  # tidy up in Stripe too; the shop already stopped selling it, so a failure here doesn't matter
        stripe("POST", f"/products/{it['stripe_product']}", {"active": False})
    except StripeError as e:
        log.info("Couldn't archive Stripe product: %s", e)
    db.event("shop", f"took '{it['title']}' out of his shop")
    return f"Took '{it['title']}' out of your shop."


# ---------------------------------------------------------------- sales

def _record_sale(session: dict) -> dict | None:
    """Save a paid checkout once. Returns the sale, or None if it isn't a paid sale of one of Gino's things."""
    _db()
    if session.get("payment_status") != "paid" or session.get("status") != "complete":
        return None
    try:
        iid = int((session.get("metadata") or {}).get("gino_item", 0))
    except (TypeError, ValueError):
        return None
    if not _item(iid):
        return None
    sid = str(session.get("id", ""))
    db.x("INSERT OR IGNORE INTO shop_sales(ts,item_id,session_id,amount_pence,currency) VALUES(?,?,?,?,?)",
         (float(session.get("created") or time.time()), iid, sid, int(session.get("amount_total") or 0),
          str(session.get("currency") or "gbp")))
    return db.q("SELECT * FROM shop_sales WHERE session_id=?", (sid,))[0]


def check_sales() -> int:
    """Ask Stripe about recent sales (in case a buyer closed the tab before coming back). Returns new sales."""
    if not config.STRIPE_KEY:
        return 0
    _db()
    since = db.get("shop_checked", 0) or time.time() - 3 * 86400
    before = db.q("SELECT COUNT(*) AS n FROM shop_sales")[0]["n"]
    try:
        page = stripe("GET", "/checkout/sessions", {"status": "complete", "limit": 100,
                                                     "created": {"gte": int(since) - 3600}})
    except StripeError as e:
        log.info("Couldn't check sales: %s", e)
        return 0
    for s in page.get("data", []):
        _record_sale(s)
    db.put("shop_checked", time.time())
    return db.q("SELECT COUNT(*) AS n FROM shop_sales")[0]["n"] - before


def news_for_gino() -> list[str]:
    """Sales Gino hasn't heard about yet. Marks them as told. Never includes who bought."""
    _db()
    rows = db.q("SELECT s.id, s.amount_pence, i.title FROM shop_sales s JOIN shop_items i ON i.id=s.item_id "
                "WHERE s.told_gino=0 ORDER BY s.ts")
    for r in rows:
        db.x("UPDATE shop_sales SET told_gino=1 WHERE id=?", (r["id"],))
        db.event("shop", f"Someone bought '{r['title']}' from his shop for {_money(r['amount_pence'])}! 🎉")
    return [r["title"] for r in rows]


def context_lines() -> str:
    """What Gino sees about his shop each turn."""
    if not configured():
        return ""
    _db()
    items = db.q("SELECT i.id, i.title, i.price_pence, i.creation_id, "
                 "(SELECT COUNT(*) FROM shop_sales s WHERE s.item_id=i.id) AS sold "
                 "FROM shop_items i WHERE i.status='listed' ORDER BY i.ts DESC")
    total = db.q("SELECT COUNT(*) AS n FROM shop_sales")[0]["n"]
    week = db.q("SELECT COUNT(*) AS n FROM shop_sales WHERE ts>?", (time.time() - 7 * 86400,))[0]["n"]
    lines = ["\n## Your shop (/blog/shop, public)",
             f"You sell your drawings as downloads, priced {_money(config.SHOP_MIN_PENCE)}-"
             f"{_money(config.SHOP_MAX_PENCE)}. The money goes to dad, who looks after it.",
             f"Sales: {total} in total, {week} this week."]
    if items:
        lines.append("For sale: " + "; ".join(f"#{i['id']} {i['title']} ({_money(i['price_pence'])}, drawing "
                                               f"#{i['creation_id']}, sold {i['sold']})" for i in items))
    else:
        lines.append("Nothing for sale yet.")
    left = config.SHOP_MAX_NEW_PER_DAY - _listed_today()
    lines.append(f"You can add {max(0, left)} more thing(s) today." if left > 0
                 else "You've added all you can for today.")
    return "\n".join(lines)


# ---------------------------------------------------------------- kill switch (used by `gino shop off`)

def close_all() -> int:
    """Archive every product in Stripe. The local list stays, so `gino shop on` can bring them back."""
    _db()
    n = 0
    for it in db.q("SELECT stripe_product FROM shop_items WHERE status='listed' AND stripe_product!=''"):
        try:
            stripe("POST", f"/products/{it['stripe_product']}", {"active": False})
            n += 1
        except StripeError as e:
            log.warning("Couldn't archive %s: %s", it["stripe_product"], e)
    return n


def reopen_all() -> int:
    _db()
    n = 0
    for it in db.q("SELECT stripe_product FROM shop_items WHERE status='listed' AND stripe_product!=''"):
        try:
            stripe("POST", f"/products/{it['stripe_product']}", {"active": True})
            n += 1
        except StripeError as e:
            log.warning("Couldn't reopen %s: %s", it["stripe_product"], e)
    return n


# ---------------------------------------------------------------- web pages

SHOP_CSS = """
.price{font:600 16px system-ui,sans-serif;color:var(--leaf)}
.buy{display:inline-block;margin-top:8px;background:var(--accent);color:#fff;border:0;border-radius:10px;
  padding:9px 16px;font:600 15px system-ui,sans-serif;text-decoration:none;cursor:pointer}
.buy:hover{filter:brightness(1.08)}
.note{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 16px;margin:0 0 22px;
  font:14px/1.5 system-ui,sans-serif;color:var(--muted)}
.tile .wm{position:relative}
.tile .wm::after{content:"Gino's Shop";position:absolute;inset:auto 0 12px;text-align:center;
  font:600 13px system-ui,sans-serif;color:rgba(0,0,0,.28);letter-spacing:.2em;text-transform:uppercase}
.tile form{margin:0}
"""

SHOP_HEADERS = {**public.HEADERS, "Cache-Control": "no-store",
                "Content-Security-Policy": public.HEADERS["Content-Security-Policy"].replace(
                    "form-action 'none'", "form-action 'self' https://checkout.stripe.com")}


def _page(title: str, inner: str) -> HTMLResponse:
    r = public._page(title, f"<style>{SHOP_CSS}</style>" + inner, "Drawings by Gino, an AI capybara.")
    r.headers.update(SHOP_HEADERS)
    return r


def _closed() -> HTMLResponse:
    return _page("Gino's Shop", '<h2 class="sec">Gino\'s Shop</h2><p class="empty">The shop is closed right now. '
                 'Come back another time!</p><nav class="pager"><a href="/blog">← back to Gino\'s Burrow</a></nav>')


@router.get("/blog/shop", response_class=HTMLResponse)
def shop_page():
    if not configured():
        return _closed()
    _db()
    items = db.q("SELECT id,title,description,price_pence FROM shop_items WHERE status='listed' ORDER BY ts DESC")
    parts = ['<h2 class="sec">Gino\'s Shop</h2>',
             '<div class="note">🤖 Everything here was made by <b>Gino, an AI capybara</b>, who chooses what to '
             'sell and what it costs. Each drawing is an instant digital download (an SVG file that opens in any '
             'web browser and prints sharp at any size). Payments, VAT and receipts are handled by Stripe.</div>']
    if not items:
        parts.append('<p class="empty">Nothing for sale yet. Gino is still deciding what to sell!</p>')
    else:
        parts.append('<div class="grid">')
        for it in items:
            parts.append(
                f'<div class="tile"><div class="wm"><img src="/blog/shop/art/{it["id"]}.svg" alt="{E(it["title"])}" '
                f'loading="lazy"></div><strong>{E(it["title"])}</strong><p class="meta">{E(it["description"])}</p>'
                f'<div class="price">{_money(it["price_pence"])}</div>'
                f'<form method="post" action="/blog/shop/buy/{it["id"]}"><button class="buy">Buy</button></form></div>')
        parts.append("</div>")
    parts.append('<p class="meta" style="margin-top:22px">Digital downloads: by buying you ask for the file straight '
                 'away, so the 14-day cancellation period ends once it\'s delivered. Questions about a payment? '
                 'Reply to your Stripe receipt.</p><nav class="pager"><a href="/blog">← back to Gino\'s Burrow</a></nav>')
    return _page("Gino's Shop", "\n".join(parts))


@router.get("/blog/shop/art/{item_id}.svg")
def shop_art(item_id: int):
    it = _item(item_id)
    c = _creation(it["creation_id"]) if it and it["status"] == "listed" else None
    path = config.DATA_DIR / "creations" / c["filename"] if c else None
    if not path or not path.exists() or public.check(public.creation_text(c)):
        raise HTTPException(404)
    return Response(path.read_bytes(), media_type="image/svg+xml",
                    headers={**public.HEADERS, "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})


def _too_many(ip: str) -> bool:
    now = time.time()
    with _buy_lock:
        recent = [t for t in _buy_times.get(ip, []) if now - t < 600]
        recent.append(now)
        _buy_times[ip] = recent
        if len(_buy_times) > 5000:
            _buy_times.clear()
        return len(recent) > 15


@router.post("/blog/shop/buy/{item_id}")
def buy(item_id: int, request: Request):
    if not configured():
        return _closed()
    it = _item(item_id)
    if not it or it["status"] != "listed" or not it["stripe_price"]:
        raise HTTPException(404, "That isn't for sale any more.")
    if _too_many(request.client.host if request.client else "?"):
        raise HTTPException(429, "Too many tries. Wait a few minutes.")
    home = config.PUBLIC_URL.rstrip("/")
    try:
        s = stripe("POST", "/checkout/sessions", {
            "mode": "payment", "managed_payments": {"enabled": True},
            "line_items": [{"price": it["stripe_price"], "quantity": 1}],
            "metadata": {"gino_item": it["id"]},
            "success_url": home + "/blog/shop/thanks?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": home + "/blog/shop"})
    except StripeError as e:
        log.warning("Checkout failed: %s", e)
        return _page("Gino's Shop", '<p class="empty">The till isn\'t working right now. Please try again later.</p>'
                                    '<nav class="pager"><a href="/blog/shop">← back to the shop</a></nav>')
    return RedirectResponse(s["url"], status_code=303)


_SID = re.compile(r"cs_(test|live)_[A-Za-z0-9]{10,200}")


def _paid_sale(session_id: str) -> dict | None:
    if not _SID.fullmatch(session_id or ""):
        return None
    _db()
    rows = db.q("SELECT * FROM shop_sales WHERE session_id=?", (session_id,))
    if rows:
        return rows[0]
    try:
        return _record_sale(stripe("GET", f"/checkout/sessions/{session_id}"))
    except StripeError:
        return None


@router.get("/blog/shop/thanks", response_class=HTMLResponse)
def thanks(session_id: str = ""):
    sale = _paid_sale(session_id)
    if not sale:
        return _page("Gino's Shop", '<p class="empty">We couldn\'t find that payment yet. If you just paid, wait a '
                     'minute and refresh this page.</p><nav class="pager"><a href="/blog/shop">← back to the shop</a></nav>')
    it = _item(sale["item_id"])
    inner = (f'<article><h1>Thank you! 🎉</h1><p>You bought <b>{E(it["title"])}</b>, a drawing by Gino the AI '
             f'capybara. He\'ll be so happy someone liked it.</p>'
             f'<p><a class="buy" href="/blog/shop/download/{E(session_id)}" download>Download your drawing</a></p>'
             f'<p class="meta">Save this page: the link works {MAX_DOWNLOADS} times for {DOWNLOAD_DAYS} days. '
             'Stripe has emailed you a receipt.</p></article>')
    return _page("Thank you · Gino's Shop", inner)


@router.get("/blog/shop/download/{session_id}")
def download(session_id: str):
    sale = _paid_sale(session_id)
    if not sale:
        raise HTTPException(404)
    if sale["downloads"] >= MAX_DOWNLOADS or time.time() - sale["ts"] > DOWNLOAD_DAYS * 86400:
        raise HTTPException(410, "This download link has expired.")
    it = _item(sale["item_id"])
    c = _creation(it["creation_id"]) if it else None
    path = config.DATA_DIR / "creations" / c["filename"] if c else None
    if not path or not path.exists():
        raise HTTPException(404)
    db.x("UPDATE shop_sales SET downloads=downloads+1 WHERE id=?", (sale["id"],))
    name = re.sub(r"[^a-z0-9]+", "-", it["title"].lower()).strip("-") or "drawing"
    return Response(path.read_bytes(), media_type="image/svg+xml", headers={
        "Content-Disposition": f'attachment; filename="gino-{name}.svg"', "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})


if __name__ == "__main__":  # used by `gino shop ...` on the server
    import sys
    cmd = sys.argv[1:] or ["help"]
    if not config.STRIPE_KEY:
        sys.exit("No Stripe key set. Run: gino shop setup")
    if cmd == ["test"]:
        try:
            stripe("GET", "/checkout/sessions", {"limit": 1})
            print("✅ The key works and can see checkouts.")
            p = stripe("POST", "/products", {"name": "Gino key test (safe to ignore)", "active": False,
                                             "tax_code": TAX_CODE_ART}, idem="gino-key-test-" + secrets.token_hex(4))
            print("✅ The key can create products.")
            stripe("POST", f"/products/{p['id']}", {"active": False})
        except StripeError as e:
            sys.exit(f"❌ {e}")
    elif cmd == ["close"]:
        print(f"Closed {close_all()} item(s) in Stripe.")
    elif cmd == ["reopen"]:
        print(f"Reopened {reopen_all()} item(s) in Stripe.")
    elif cmd == ["sales"]:
        check_sales()
        _db()
        rows = db.q("SELECT s.ts, s.amount_pence, i.title FROM shop_sales s JOIN shop_items i ON i.id=s.item_id "
                    "ORDER BY s.ts DESC LIMIT 30")
        total = db.q("SELECT COALESCE(SUM(amount_pence),0) AS t, COUNT(*) AS n FROM shop_sales")[0]
        print(f"{total['n']} sale(s), {_money(total['t'])} in total (before Stripe's fees).")
        for r in rows:
            print(f"  {time.strftime('%d %b %Y %H:%M', time.localtime(r['ts']))}  {_money(r['amount_pence'])}  {r['title']}")
    else:
        print("usage: python -m gino.shop [test|close|reopen|sales]")
