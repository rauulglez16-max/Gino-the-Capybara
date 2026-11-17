"""Gino's long-term storage: one SQLite file holds his whole life."""
import json
import sqlite3
import threading
import time
from typing import Any

from . import config

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, text TEXT NOT NULL,
  importance INTEGER NOT NULL DEFAULT 2 CHECK (importance BETWEEN 1 AND 5), tags TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS journal (id INTEGER PRIMARY KEY, ts REAL NOT NULL, text TEXT NOT NULL, emotion TEXT);
CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, title TEXT NOT NULL, why TEXT NOT NULL DEFAULT '',
  steps TEXT NOT NULL DEFAULT '', progress TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','done','dropped')), updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS habitat (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, name TEXT NOT NULL, emoji TEXT NOT NULL,
  x INTEGER NOT NULL, y INTEGER NOT NULL, description TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS creations (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
  filename TEXT NOT NULL, note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS chat (id INTEGER PRIMARY KEY, ts REAL NOT NULL, sender TEXT NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts REAL NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS spend (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, day TEXT NOT NULL, purpose TEXT NOT NULL, model TEXT NOT NULL,
  input_tokens INTEGER, output_tokens INTEGER, cache_read INTEGER, cache_write INTEGER, usd REAL NOT NULL);
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, updated REAL NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('diary','page')), slug TEXT NOT NULL, title TEXT NOT NULL,
  body TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '', creation_id INTEGER REFERENCES creations(id),
  UNIQUE (kind, slug));
CREATE TABLE IF NOT EXISTS social_posts (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, text TEXT NOT NULL, uri TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('posted','failed')));
CREATE TABLE IF NOT EXISTS dreams (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, title TEXT NOT NULL, story TEXT NOT NULL,
  symbols TEXT NOT NULL DEFAULT '[]', colours TEXT NOT NULL DEFAULT '', feeling TEXT NOT NULL DEFAULT '',
  intensity INTEGER NOT NULL DEFAULT 3, longing TEXT NOT NULL DEFAULT '', sources TEXT NOT NULL DEFAULT '',
  strangeness INTEGER NOT NULL DEFAULT 2 CHECK (strangeness BETWEEN 1 AND 5),
  creation_id INTEGER REFERENCES creations(id));
CREATE INDEX IF NOT EXISTS spend_day ON spend(day);
CREATE INDEX IF NOT EXISTS events_ts ON events(ts);
"""


def conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, isolation_level=None)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.executescript(SCHEMA)
            have = {r["name"] for r in _conn.execute("PRAGMA table_info(habitat)")}
            for col, ddl in (("kind", "TEXT NOT NULL DEFAULT ''"), ("color", "TEXT NOT NULL DEFAULT ''"),
                             ("size", "REAL NOT NULL DEFAULT 1")):
                if col not in have:
                    _conn.execute(f"ALTER TABLE habitat ADD COLUMN {col} {ddl}")
            have = {r["name"] for r in _conn.execute("PRAGMA table_info(creations)")}
            if "dream_id" not in have:  # a painting of one of his dreams
                _conn.execute("ALTER TABLE creations ADD COLUMN dream_id INTEGER")
            have = {r["name"] for r in _conn.execute("PRAGMA table_info(social_posts)")}
            for col, ddl in (("photo", "TEXT NOT NULL DEFAULT ''"), ("alt", "TEXT NOT NULL DEFAULT ''")):
                if col not in have:
                    _conn.execute(f"ALTER TABLE social_posts ADD COLUMN {col} {ddl}")
        return _conn


def q(sql: str, args: tuple = ()) -> list[dict]:
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def x(sql: str, args: tuple = ()) -> int:
    with _lock:
        cur = conn().execute(sql, args)
        return cur.lastrowid or 0


def get(key: str, default: Any = None) -> Any:
    rows = q("SELECT value FROM kv WHERE key=?", (key,))
    return json.loads(rows[0]["value"]) if rows else default


def put(key: str, value: Any) -> None:
    x("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
      (key, json.dumps(value)))


def event(kind: str, text: str) -> None:
    x("INSERT INTO events(ts,kind,text) VALUES(?,?,?)", (time.time(), kind, text[:2000]))
