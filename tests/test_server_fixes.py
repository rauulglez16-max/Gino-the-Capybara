"""The 2026-11-26 server check-up: small bugs that cost the server time, money accounting or stray processes."""
import subprocess
import threading
import time
from types import SimpleNamespace

import pytest

from gino import brain, clips, config, db, public, server, social, stream, vitals


def test_the_privacy_filter_still_spots_a_new_quote_from_dad():
    """Dad's sentences are remembered between checks (much faster), but a new message is picked up straight away."""
    line = "my favourite place in the whole world is the little bakery on the corner"
    assert public.check(f"Today I thought: {line}.") is None
    db.x("INSERT INTO chat(ts,sender,text) VALUES(?,?,?)", (time.time(), "dad", line.capitalize() + "!"))
    assert "private chats" in public.check(f"Today I thought: {line}.")
    db.x("DELETE FROM chat")
    assert public.check(f"Today I thought: {line}.") is None


def _resp(model):
    usage = SimpleNamespace(input_tokens=1_000_000, output_tokens=0, cache_read_input_tokens=0,
                            cache_creation_input_tokens=0, server_tool_use=None)
    return SimpleNamespace(model=model, usage=usage)


def test_a_fallback_model_is_counted_at_its_own_price():
    """If Claude hands a request to another model, the money guard counts what that model really costs."""
    assert brain.record_spend("turn", _resp("claude-opus-5"), "claude-opus-5-5") == pytest.approx(5.0)
    assert brain.record_spend("turn", _resp("claude-fable-5-1"), "claude-opus-5-5") == pytest.approx(10.0)
    # a model with no known price is counted at the dearest one, never the cheapest
    assert brain.record_spend("turn", _resp("claude-unknown-9"), "claude-opus-5-5") == pytest.approx(10.0)


def test_shop_news_never_waits_for_gino_to_finish_thinking(monkeypatch):
    """Waiting here used to stop his whole heartbeat until the turn was over."""
    monkeypatch.setattr(config, "STRIPE_KEY", "rk_test_x")
    monkeypatch.setattr(server.shop, "check_sales", lambda: 0)
    monkeypatch.setattr(server.shop, "news_for_gino", lambda: ["Moon study"])
    monkeypatch.setattr(server.telegram, "send", lambda text: True)
    fun = vitals.load()["fun"]
    with brain.mind_lock:  # he's in the middle of a turn
        t0 = time.time()
        assert server.shop_news() is False  # comes back at once; the news waits for the next heartbeat
        assert time.time() - t0 < 1
    assert server.shop_news(check=False) is True
    assert vitals.load()["fun"] > fun or fun == 100


def test_two_presses_of_make_a_video_film_only_one(monkeypatch):
    db.x("DELETE FROM clips")
    monkeypatch.setattr(clips, "available", lambda: True)

    def slow_add(kind, by, caption=""):
        time.sleep(0.2)  # planning a video takes a moment: long enough for a second press to slip in
        cid = db.x("INSERT INTO clips(ts,kind,title,status) VALUES(?,?,?,'making')", (time.time(), "day", "x"))
        return cid, {}
    monkeypatch.setattr(clips, "_add", slow_add)
    results = []

    def press():
        try:
            results.append(clips.make("day", by="dad"))
        except RuntimeError as e:
            results.append(str(e))
    presses = [threading.Thread(target=press) for _ in range(2)]
    monkeypatch.setattr(clips, "_film_all", lambda jobs: None)  # nothing really films
    for p in presses:
        p.start()
    for p in presses:
        p.join()
    assert sum(isinstance(r, int) for r in results) == 1
    assert db.q("SELECT COUNT(*) AS n FROM clips WHERE status='making'")[0]["n"] == 1
    db.x("DELETE FROM clips")


def test_a_photo_post_on_its_way_counts_as_a_post(monkeypatch):
    db.x("DELETE FROM social_posts")
    monkeypatch.setattr(social, "configured", lambda: True)
    monkeypatch.setattr(social.photo, "available", lambda: True)
    monkeypatch.setattr(social.photo, "scene_state", lambda: {})
    started = []
    monkeypatch.setattr(social.threading, "Thread", lambda target, args, **k: SimpleNamespace(
        start=lambda: started.append(args)))
    try:
        said = social.post("The pond is glittering today.", "wide")
        assert said.startswith("Posting") and len(started) == 1
        assert social.wait_minutes() >= 1  # no second post sneaks in while the photo is being taken
        assert social.post("Another one!", "selfie").startswith("Not posted")
    finally:
        social._photo_post["busy"] = False


def test_a_stuck_tv_scene_is_stopped_with_its_browser_and_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(stream, "scene_job", lambda platform: {})
    monkeypatch.setattr(stream, "folder", lambda platform: tmp_path)
    killed, kw = [], {}

    class Stuck:
        pid, returncode, calls = 31337, None, 0

        def communicate(self, data=None, timeout=None):
            Stuck.calls += 1
            if Stuck.calls == 1:
                raise subprocess.TimeoutExpired("render", timeout)
            self.returncode = -9
            return b"", b""

        def kill(self):
            pytest.fail("only the helper was stopped, not its whole group")

    monkeypatch.setattr(stream.subprocess, "Popen", lambda cmd, **k: kw.update(k) or Stuck())
    monkeypatch.setattr(stream.os, "killpg", lambda pgid, sig: killed.append(pgid))
    with pytest.raises(RuntimeError, match="took too long"):
        stream.film_scene("youtube")
    assert kw.get("start_new_session") and killed == [31337]
