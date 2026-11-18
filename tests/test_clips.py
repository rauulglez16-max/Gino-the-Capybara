"""Gino's videos: the story of each clip, what goes in it (only public-safe things) and the TikTok rules."""
import time

import pytest

from gino import clips, config, db, public, tiktok, tools, vitals


def body():
    b = vitals.load()
    b.update(energy=90, fun=50, pos=[5, 5])
    return b


def words(job) -> str:
    """Every bit of text a clip shows or posts."""
    caps = [c["text"] for s in job["shots"] for c in s.get("captions", [])]
    return "\n".join([job["title"], job["caption"], *job["end"], *caps])


def paint(title, dream=False, publish=True):
    b = body()
    did = None
    if dream:
        from gino import dreams
        did = dreams.save(b, {"title": title, "story": "I floated over the lake.", "feeling": "dreamy"}, 3)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>'
    tools.run("create", {"kind": "svg", "title": title, "content": svg, **({"dream_id": did} if did else {})}, b)
    cid = db.q("SELECT id FROM creations ORDER BY id DESC LIMIT 1")[0]["id"]
    if publish:
        public.write_page(title, "A painting.", creation_id=cid)
    return cid


@pytest.fixture(autouse=True)
def no_clips():
    db.x("DELETE FROM clips")
    yield


@pytest.mark.parametrize("kind", clips.KINDS)
def test_every_kind_of_clip_is_a_short_vertical_story(kind):
    job = clips.plan(kind)
    total = sum(s["dur"] for s in job["shots"])
    assert 15 <= total <= 30
    assert (job["width"], job["height"]) == (720, 1280)
    assert 23 <= job["fps"] <= 30
    assert "#capybara" in job["caption"] and len(job["caption"]) <= 2000
    assert public.check(words(job)) is None
    # the sounds cover the whole clip, one piece after another
    assert job["sounds"][0][1] == 0 and job["sounds"][-1][2] == pytest.approx(total)


def test_a_dream_clip_only_shows_paintings_that_are_already_public():
    paint("Secret dream", dream=True, publish=False)
    assert clips.plan("dream")["kind"] == "night"  # nothing public to show, so a different story
    cid = paint("Moon soup", dream=True)
    job = clips.plan("dream")
    assert job["kind"] == "dream" and job["source"] == f"art:{cid}"
    assert any(s.get("art") == f"/blog/art/{cid}.svg" for s in job["shots"])
    assert "Moon soup" in job["caption"]


def test_private_names_never_reach_a_clip():
    tools.run("build", {"name": "Dad's bench", "emoji": "🪑", "x": 3, "y": 2, "kind": "bench",
                        "story": "Raul and I sit here in Valencia."}, body())
    job = clips.plan("made")
    text = words(job)
    assert "Dad" not in text and "Raul" not in text and "Valencia" not in text
    assert "bench" in text  # the harmless part of the name survives


def test_the_daily_pick_prefers_fresh_dreams_then_new_things():
    assert clips.best_kind() in ("day", "night")
    tools.run("build", {"name": "lantern", "emoji": "🏮", "x": 1, "y": 1}, body())
    assert clips.best_kind() == "made"
    paint("Starfish rain", dream=True)
    assert clips.best_kind() == "dream"


def test_the_sound_follows_day_night_and_rain():
    plan = clips._sound_plan([{"dur": 5, "hour": [8, 10]}, {"dur": 5, "hour": [12, 17]},
                              {"dur": 5, "hour": [22, 23]}, {"dur": 5, "hour": [23, 24], "weather": "rain"}])
    assert [p[0] for p in plan] == ["day", "night", "rain"]
    assert plan[0][1:] == [0, 10]
    args, graph = clips._audio_args(plan, 20)
    assert args.count("-i") == 3 and graph.count("acrossfade") == 2 and graph.endswith("[aout]")


def test_the_camera_is_off_by_default():
    assert not clips.available()
    with pytest.raises(RuntimeError):
        clips.make("day")
    assert "make_clip" not in [t["name"] for t in tools.all_tools()]


def test_gino_cant_film_with_a_private_caption(monkeypatch):
    monkeypatch.setattr(clips, "available", lambda: True)
    started = []
    monkeypatch.setattr(clips, "make", lambda kind, by, caption: started.append((kind, by, caption)) or 7)
    r = tools.run("make_clip", {"story": "day", "caption": "Filmed for my dad Raul"}, body())
    assert r.startswith("Not filmed") and not started
    r = tools.run("make_clip", {"story": "night", "caption": "My night under the stars"}, body())
    assert "#7" in r and started == [("night", "gino", "My night under the stars")]


def test_old_videos_are_tidied_away(monkeypatch, tmp_path):
    monkeypatch.setattr(clips, "CLIPS_DIR", tmp_path)
    for i in range(clips.KEEP + 3):
        name = f"gino-{i}.mp4"
        (tmp_path / name).write_bytes(b"x")
        db.x("INSERT INTO clips(ts,kind,title,status,filename) VALUES(?,?,?,?,?)",
             (time.time(), "day", "t", "ready", name))
    clips._tidy()
    assert len(list(tmp_path.iterdir())) == clips.KEEP
    assert db.q("SELECT COUNT(*) AS n FROM clips WHERE filename=''")[0]["n"] == 3


# ---------------------------------------------------------------- TikTok

def test_tiktok_is_off_until_set_up():
    s = tiktok.status()
    assert not s["configured"] and not s["connected"] and s["mode"] == "drafts" and not s["auto"]
    with pytest.raises(RuntimeError):
        tiktok.connect_url()


def test_tiktok_connect_needs_the_state_from_dads_page(monkeypatch):
    monkeypatch.setattr(config, "TIKTOK_CLIENT_KEY", "ck")
    monkeypatch.setattr(config, "TIKTOK_CLIENT_SECRET", "cs")
    monkeypatch.setattr(config, "PUBLIC_URL", "https://ginothecapybara.com")
    url = tiktok.connect_url()
    assert "video.upload" in url and "video.publish" not in url
    assert "redirect_uri=https%3A%2F%2Fginothecapybara.com%2Ftiktok%2Fcallback" in url
    with pytest.raises(RuntimeError, match="old"):
        tiktok.finish_connect("code", "forged-state")


def test_tiktok_refuses_a_private_caption(monkeypatch, tmp_path):
    monkeypatch.setattr(tiktok, "connected", lambda: True)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 20000)
    monkeypatch.setattr(clips, "path", lambda cid: video)
    cid = db.x("INSERT INTO clips(ts,kind,title,caption,status,filename) VALUES(?,?,?,?,?,?)",
               (time.time(), "day", "t", "A day 🌿", "ready", "v.mp4"))
    monkeypatch.setattr(tiktok, "_api", lambda *a, **k: pytest.fail("nothing should be sent"))
    with pytest.raises(RuntimeError, match="private"):
        tiktok.send(cid, title="Hi from Raul's capybara")


def test_direct_posts_are_labelled_ai_and_respect_tiktoks_choices(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TIKTOK_MODE", "direct")
    monkeypatch.setattr(tiktok, "connected", lambda: True)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 20000)
    monkeypatch.setattr(clips, "path", lambda cid: video)
    cid = db.x("INSERT INTO clips(ts,kind,title,caption,status,filename,seconds) VALUES(?,?,?,?,?,?,?)",
               (time.time(), "day", "t", "A day 🌿", "ready", "v.mp4", 20))
    calls = []

    def api(path, body=None):
        calls.append((path, body))
        if path.endswith("creator_info/query/"):
            return {"creator_nickname": "Gino", "privacy_level_options": ["SELF_ONLY", "PUBLIC_TO_EVERYONE"],
                    "comment_disabled": True, "max_video_post_duration_sec": 600}
        return {"publish_id": "p1", "upload_url": "https://upload.example/x"}
    monkeypatch.setattr(tiktok, "_api", api)
    monkeypatch.setattr(tiktok, "_http", lambda *a, **k: (201, {}))
    monkeypatch.setattr(tiktok, "_watch", lambda *a: None)
    with pytest.raises(RuntimeError, match="Choose who"):
        tiktok.send(cid, privacy="")
    db.x("UPDATE clips SET tiktok_status='' WHERE id=?", (cid,))
    msg = tiktok.send(cid, privacy="PUBLIC_TO_EVERYONE", allow_comment=True)
    assert "Sent" in msg
    init = [b for p, b in calls if p.endswith("/video/init/")][-1]
    assert init["post_info"]["is_aigc"] is True
    assert init["post_info"]["disable_comment"] is True  # TikTok says comments are off for this account
    assert init["source_info"] == {"source": "FILE_UPLOAD", "video_size": 20000, "chunk_size": 20000,
                                   "total_chunk_count": 1}
    with pytest.raises(RuntimeError, match="already"):
        tiktok.send(cid, privacy="PUBLIC_TO_EVERYONE")


# ---------------------------------------------------------------- polishing on dad's PC (FilmCraft)

def ready_clip(tmp_path, kind="day", **cols):
    (tmp_path / f"gino-x-{kind}.mp4").write_bytes(b"\0\0\0\x18ftypisom" + b"\0" * 20_000)
    names = ["ts", "kind", "title", "caption", "status", "filename", *cols]
    vals = [time.time(), kind, "A day in Gino's life", "cap", "ready", f"gino-x-{kind}.mp4", *cols.values()]
    return db.x(f"INSERT INTO clips({','.join(names)}) VALUES({','.join('?' * len(names))})", tuple(vals))


def test_the_script_has_every_caption_at_the_right_moment():
    job = clips.plan("day")
    s = clips.script(job)
    assert s["seconds"] == pytest.approx(sum(sh["dur"] for sh in job["shots"]))
    texts = [c["text"] for sh in job["shots"] for c in sh.get("captions", [])]
    assert [l["text"] for l in s["lines"]] == texts
    assert s["lines"][0]["at"] == 2.0  # "Good morning" shows 2 s into the first shot
    assert s["lines"][1]["at"] == pytest.approx(job["shots"][0]["dur"] + 0.3)
    assert all(0 <= l["at"] < l["until"] <= s["seconds"] for l in s["lines"])


def test_a_polished_video_replaces_the_original_everywhere(monkeypatch, tmp_path):
    monkeypatch.setattr(clips, "CLIPS_DIR", tmp_path)
    cid = ready_clip(tmp_path)
    assert [c["id"] for c in clips.polish_queue()] == [cid] and clips.polisher_on()
    with pytest.raises(RuntimeError):
        clips.save_polished(cid, b"<html>not a video</html>" * 1000)
    video = b"\0\0\0\x18ftypisom" + b"\1" * 30_000
    clips.save_polished(cid, video)
    assert clips.path(cid).read_bytes() == video  # the Videos tab and TikTok get the polished one
    assert clips.path(cid, raw=True).name == "gino-x-day.mp4"
    assert clips.listing()[0]["polished"] is True
    assert clips.polish_queue() == []  # not polished twice


def test_clips_already_on_tiktok_or_that_failed_arent_polished(monkeypatch, tmp_path):
    monkeypatch.setattr(clips, "CLIPS_DIR", tmp_path)
    sent = ready_clip(tmp_path, tiktok_status="posted")
    with pytest.raises(RuntimeError):
        clips.save_polished(sent, b"\0\0\0\x18ftypisom" + b"\1" * 30_000)
    bad = ready_clip(tmp_path, "night")
    clips.polish_failed(bad, "FilmCraft crashed")
    assert clips.polish_queue() == []


def test_the_daily_video_waits_for_the_polisher_only_while_dads_pc_is_on(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TIKTOK_AUTO", True)
    monkeypatch.setattr(tiktok, "connected", lambda: True)
    sent, waited = [], []
    monkeypatch.setattr(tiktok, "_auto_send", lambda cid: sent.append(cid))
    monkeypatch.setattr(tiktok.threading, "Thread", lambda target, args, **k: type(
        "T", (), {"start": lambda self: waited.append(args[0])})())
    cid = db.x("INSERT INTO clips(ts,kind,title,status,made_by) VALUES(?,?,?,?,?)", (time.time(), "day", "t", "ready", "auto"))
    db.put("polisher_seen", 0)
    tiktok.after_clip(cid)
    assert sent == [cid] and waited == []  # PC off: straight away, as before
    db.put("polisher_seen", time.time())
    tiktok.after_clip(cid)
    assert waited == [cid]
    db.x("UPDATE clips SET polished='p.mp4' WHERE id=?", (cid,))
    tiktok._send_when_polished(cid, wait=5, step=0.01)
    assert sent == [cid, cid]


def test_the_polisher_needs_the_password(monkeypatch):
    from fastapi.testclient import TestClient
    from gino import server
    monkeypatch.setattr(config, "PASSWORD", "pw")
    c = TestClient(server.app)
    assert c.get("/api/clips/polish").status_code == 401
    assert c.put("/api/clips/1/polished", content=b"x").status_code == 401
    assert c.get("/api/clips/polish", headers={"x-gino-key": "pw"}).json() == {"clips": []}
