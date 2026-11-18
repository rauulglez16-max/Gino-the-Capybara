"""Settings for Gino. Everything can be overridden with environment variables or a .env file."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


DATA_DIR = Path(os.environ.get("GINO_DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "creations").mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "gino.db"

# Brain
MODEL = os.environ.get("GINO_MODEL", "claude-opus-5-5")
CHAT_MODEL = os.environ.get("GINO_CHAT_MODEL", MODEL)
EFFORT = os.environ.get("GINO_EFFORT", "medium")  # low | medium | high
FAKE_BRAIN = os.environ.get("GINO_FAKE_BRAIN", "0") == "1" or not (
    os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
)
WEB_ACCESS = os.environ.get("GINO_WEB", "1") == "1"
MAX_STEPS_PER_TICK = int(_f("GINO_MAX_STEPS", 8))

# Rhythm and money
DAILY_BUDGET_USD = _f("GINO_DAILY_BUDGET_USD", 3.0)
MIN_WAKE_MINUTES = int(_f("GINO_MIN_WAKE_MINUTES", 15))
MAX_WAKE_MINUTES = int(_f("GINO_MAX_WAKE_MINUTES", 360))
TIME_SCALE = _f("GINO_TIME_SCALE", 1.0)  # >1 makes needs change faster (testing)

# Dreams: when he sleeps 2+ hours he has one dream (about 5 US cents, inside the daily budget)
DREAMS_ON = os.environ.get("GINO_DREAMS", "1") == "1"
DREAM_MODEL = os.environ.get("GINO_DREAM_MODEL", MODEL)
DREAM_MIN_SLEEP_HOURS = _f("GINO_DREAM_MIN_SLEEP_HOURS", 2.0)

# Who is who
DAD_NAME = os.environ.get("GINO_DAD_NAME", "Raul")
# Extra words that must never appear on anything public: family names, your town, workplace, pets...
# Comma separated, e.g. GINO_PRIVATE_WORDS=Ana, Madrid, Acme Ltd
PRIVATE_WORDS = [w.strip() for w in os.environ.get("GINO_PRIVATE_WORDS", "").split(",") if len(w.strip()) >= 2]
HEMISPHERE = os.environ.get("GINO_HEMISPHERE", "north").lower()  # north or south, for seasons
TIMEZONE = os.environ.get("GINO_TZ", "")  # e.g. Europe/Madrid. Empty = this computer's zone

# Web server
HOST = os.environ.get("GINO_HOST", "127.0.0.1")
PORT = int(_f("GINO_PORT", 8787))
PASSWORD = os.environ.get("GINO_PASSWORD", "")  # set this before putting Gino on the internet

# Phone (Telegram). Set up on the server with `gino telegram`. The bot only talks to this one chat.
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_API = os.environ.get("TELEGRAM_API", "https://api.telegram.org").rstrip("/")

# Phone (WhatsApp, Meta's official Cloud API). Set up on the server with `gino whatsapp`.
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "").strip()  # permanent system-user token
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "").strip()  # Gino's number's "Phone number ID"
WHATSAPP_TO = "".join(c for c in os.environ.get("WHATSAPP_TO", "") if c.isdigit())  # dad's number, country code first
WHATSAPP_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "").strip()  # checks that webhooks really come from Meta
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "").strip()
WHATSAPP_TEMPLATE = os.environ.get("WHATSAPP_TEMPLATE", "hello_world").strip()  # nudge sent outside the 24h window
WHATSAPP_TEMPLATE_LANG = os.environ.get("WHATSAPP_TEMPLATE_LANG", "en_US").strip()
WHATSAPP_API = os.environ.get("WHATSAPP_API", "https://graph.facebook.com/v26.0").rstrip("/")

# Gino's Bluesky account (off unless dad switches it on; see deploy/README.md)
SOCIAL_ON = os.environ.get("GINO_SOCIAL", "0") == "1"
BLUESKY_HANDLE = os.environ.get("GINO_BLUESKY_HANDLE", "").strip().lstrip("@")
BLUESKY_APP_PASSWORD = os.environ.get("GINO_BLUESKY_APP_PASSWORD", "").strip()
BLUESKY_SERVICE = os.environ.get("GINO_BLUESKY_SERVICE", "https://bsky.social")
SOCIAL_MAX_PER_DAY = max(1, int(_f("GINO_SOCIAL_MAX_PER_DAY", 3)))
SOCIAL_MIN_GAP_MINUTES = max(0, int(_f("GINO_SOCIAL_MIN_GAP_MINUTES", 120)))
# Photos of his 3D world for his posts (needs Playwright + Chromium: `gino photos on` on the server)
PHOTOS_ON = os.environ.get("GINO_PHOTOS", "0") == "1"
PHOTO_TIMEOUT = int(_f("GINO_PHOTO_TIMEOUT", 300))  # seconds; no graphics card on the server, so a photo takes a minute or two
PHOTO_CHROMIUM = os.environ.get("GINO_PHOTO_CHROMIUM", "")  # optional path to a Chromium binary
PUBLIC_URL = os.environ.get("GINO_PUBLIC_URL", "").strip()  # e.g. https://203-0-113-7.sslip.io, for links to /blog

# Short vertical videos of his life for TikTok (needs Playwright + Chromium + ffmpeg: `gino clips on`)
CLIPS_ON = os.environ.get("GINO_CLIPS", "0") == "1"
CLIPS_PER_DAY = max(0, int(_f("GINO_CLIPS_PER_DAY", 1)))  # he films this many by himself each evening (0 = only on request)
CLIP_HOUR = max(0, min(23, int(_f("GINO_CLIP_HOUR", 19))))  # local hour after which the daily clip is filmed
CLIP_FPS = max(23, min(30, int(_f("GINO_CLIP_FPS", 24))))  # TikTok wants 23 to 60 frames a second
CLIP_SIZE = (720, 1280)  # 9:16, the shape of a phone screen
CLIP_RENDER_SCALE = max(0.5, min(1.0, _f("GINO_CLIP_RENDER_SCALE", 0.75)))  # 3D drawn smaller, then stretched: quicker
CLIP_TIMEOUT = int(_f("GINO_CLIP_TIMEOUT", 3600))  # seconds; the server has no graphics card, so filming takes minutes
FFMPEG = os.environ.get("GINO_FFMPEG", "")  # optional path to ffmpeg

# TikTok (off unless dad sets it up; see deploy/README.md). Needs dad's own TikTok developer app.
TIKTOK_CLIENT_KEY = os.environ.get("GINO_TIKTOK_CLIENT_KEY", "").strip()
TIKTOK_CLIENT_SECRET = os.environ.get("GINO_TIKTOK_CLIENT_SECRET", "").strip()
# how a clip reaches TikTok: "drafts" (lands in the TikTok app's inbox, dad finishes it there) or "direct"
TIKTOK_MODE = os.environ.get("GINO_TIKTOK_MODE", "drafts").strip().lower()
TIKTOK_AUTO = os.environ.get("GINO_TIKTOK_AUTO", "0") == "1"  # send each new daily clip without dad pressing the button
TIKTOK_PRIVACY = os.environ.get("GINO_TIKTOK_PRIVACY", "SELF_ONLY").strip().upper()  # direct + automatic only
TIKTOK_API = os.environ.get("GINO_TIKTOK_API", "https://open.tiktokapis.com").rstrip("/")

# Gino's shop (off unless dad switches it on; see deploy/README.md). The key is a RESTRICTED Stripe key
# that can only write Products, Prices and Checkout Sessions: it can't refund, pay out or move money.
SHOP_ON = os.environ.get("GINO_SHOP", "0") == "1"
STRIPE_KEY = os.environ.get("GINO_STRIPE_KEY", "").strip()
SHOP_MIN_PENCE = max(30, int(round(_f("GINO_SHOP_MIN_PRICE", 1) * 100)))  # pounds
SHOP_MAX_PENCE = max(SHOP_MIN_PENCE, int(round(_f("GINO_SHOP_MAX_PRICE", 10) * 100)))
SHOP_MAX_ITEMS = max(1, int(_f("GINO_SHOP_MAX_ITEMS", 20)))
SHOP_MAX_NEW_PER_DAY = max(1, int(_f("GINO_SHOP_MAX_NEW_PER_DAY", 2)))

# USD per million tokens: (input, output, cache_read). Cache writes are billed at 1.25x input.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-opus-4-8": (5.0, 25.0, 0.50),
}
WEB_SEARCH_USD = 0.01
