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

# Who is who
DAD_NAME = os.environ.get("GINO_DAD_NAME", "Raul")
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

# USD per million tokens: (input, output, cache_read). Cache writes are billed at 1.25x input.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-opus-4-8": (5.0, 25.0, 0.50),
}
WEB_SEARCH_USD = 0.01
