"""Shared setup: every test run gets a fresh, empty Gino in a temporary folder (never your real one)."""
import os
import tempfile

os.environ["GINO_DATA_DIR"] = tempfile.mkdtemp(prefix="gino-test-")
os.environ["GINO_FAKE_BRAIN"] = "1"
os.environ["GINO_DAD_NAME"] = "Raul"
os.environ["GINO_DAILY_BUDGET_USD"] = "3"
os.environ["GINO_PRIVATE_WORDS"] = "Valencia, Luna the cat"
for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GINO_PASSWORD"):
    os.environ.pop(k, None)

import pytest  # noqa: E402

from gino import config, db  # noqa: E402

TABLES = ("memories", "journal", "goals", "habitat", "creations", "chat", "events", "spend", "posts", "dreams", "kv")


@pytest.fixture(autouse=True)
def clean():
    for t in TABLES:
        db.x(f"DELETE FROM {t}")
    for f in (config.DATA_DIR / "creations").glob("*"):
        f.unlink()
    yield
