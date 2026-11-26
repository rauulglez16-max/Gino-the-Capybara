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
    assert (job["width"], job["height"]) == (1080, 1920)  # full HD by default
    assert job["detail"] == "fur" and job["film"] and job["crf"] <= 20
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
    assert clips.best_kind() in clips.EVERYDAY
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
    assert s["lines"][0] == {"text": "Good morning! ☀️", "at": 0.25, "until": 2.3, "speech": True}  # he says it
    assert s["lines"][1]["at"] == pytest.approx(job["shots"][0]["dur"] + 0.3) and "speech" not in s["lines"][1]
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


@pytest.mark.parametrize("kind", clips.KINDS)
def test_every_clip_opens_and_ends_on_his_face(kind):
    paint("Moon soup", dream=True)
    job = clips.plan(kind)
    first, last = job["shots"][0], job["shots"][-1]
    assert first["cam"]["around"] == "face" and first["cam"]["from"] == clips.FACE  # opens close on his face...
    assert first["cam"]["to"][0] > first["cam"]["from"][0]                           # ...then pulls back
    assert last["cam"]["around"] == "face" and last["cam"]["to"] == clips.FACE      # ends zoomed back in: it loops
    assert last["dur"] > job["end_seconds"] and not last.get("asleep")
    # a quick cut to his face somewhere in the middle, and (when awake) words beside his face
    assert any(s.get("face") for s in job["shots"][1:-1])
    assert any(c.get("style") == "speech" for s in job["shots"] for c in s["captions"])


def build(name, kind, x, y, story=""):
    db.x("INSERT INTO habitat(ts,name,emoji,x,y,kind,story) VALUES(?,?,?,?,?,?,?)",
         (time.time(), name, "✨", x, y, kind, story))


def test_a_new_thing_he_built_gets_carried_to_its_spot():
    build("Little Burrow House", "house", 3, 2)
    build("Star lamp", "lamp", 10, 7)
    job = clips.plan("made")
    item = db.q("SELECT id FROM habitat WHERE name='Star lamp'")[0]["id"]
    assert job["carry"]["id"] == item and job["carry"]["to"] == [10, 7]
    fx, fy = job["carry"]["from"]
    assert (fx, fy) != (10, 7) and 0 <= fx < 16 and 0 <= fy < 10 and (fx, fy) != (3, 2)  # a free square nearby
    assert job["start"]["facing"] == [fx, fy]
    assert sum(1 for s in job["shots"] if s.get("carry")) == 1
    follow = next(s for s in job["shots"] if s.get("carry"))
    assert follow["cam"]["around"] == "gino" and follow["cam"]["track"]  # the camera tags along behind him


def test_big_things_arent_carried_but_he_still_walks_over():
    build("Big pond", "pond", 9, 5)
    job = clips.plan("made")
    assert "carry" not in job
    assert any(s.get("go") for s in job["shots"])


def test_private_words_never_reach_a_speech_bubble():
    build("Valencia lamp", "lamp", 10, 7)
    assert public.check(words(clips.plan("made"))) is None


def test_ordinary_days_take_turns_between_the_everyday_stories():
    day = 86400
    # an empty home can't fill a tour or a "watch it grow" clip yet
    assert {clips.best_kind(time.time() + d * day) for d in range(30)} == {"day", "cute", "night"}
    for i, (kind, x) in enumerate([("bench", 2), ("lamp", 5), ("hammock", 8), ("flowers", 11), ("pond", 13)]):
        build(f"thing {i}", kind, x, 3)
    db.x("UPDATE habitat SET ts=0")  # not new any more, so they don't need a "made" clip
    assert {clips.best_kind(time.time() + d * day) for d in range(30)} == set(clips.EVERYDAY)
    # the story he filmed last isn't picked again straight away
    db.x("INSERT INTO clips(ts,kind,title,status) VALUES(?,?,?,?)", (time.time(), "cute", "x", "ready"))
    assert "cute" not in {clips.best_kind(time.time() + d * day) for d in range(30)}


def test_a_cute_clip_is_quick_cuts_of_his_poses():
    build("Lily pond", "pond", 12, 6)
    build("Tulips", "flowers", 4, 7)
    job = clips.plan("cute")
    assert job["kind"] == "cute"
    poses = [s for s in job["shots"] if not s.get("face")]
    assert len(poses) == 5 and len({s["pose"] for s in poses}) >= 4  # different moments, not the same one again
    acts = {a for a, *_ in clips.CUTE_FREE} | {a for a, *_ in clips.CUTE_AT}
    assert all(s["pose"] in acts for s in poses)
    assert {"roll", "swim"} <= {s["pose"] for s in poses}  # the cutest ones are always in
    assert poses[-1]["pose"] == "swim"  # the soak is last, so he isn't left standing in the pond
    assert all(s.get("cute") in ("hop", "roll", "orange", "stretch", "sit", "dance", "curl", "sniff")
               for s in poses if not s.get("near"))  # his own cute poses, struck facing the camera
    for s in poses:
        if s.get("near"):  # done at one of his things: right in the pond for a soak, else beside it
            item = db.q("SELECT kind FROM habitat WHERE id=?", (s["near"]["id"],))[0]["kind"]
            assert (s["near"]["dist"] == 0) == (s["pose"] == "swim") and (item == "pond") == (s["pose"] == "swim")
    # a different day, a different order
    orders = {tuple(s["pose"] for s in clips.plan("cute", d * 86400)["shots"] if not s.get("face")) for d in range(5)}
    assert len(orders) > 1


def test_a_home_tour_visits_his_things_and_tells_their_stories():
    build("Old bench", "bench", 2, 2, story="I sat here the day it first snowed.")
    build("Lantern", "lamp", 9, 3)
    build("Hammock", "hammock", 13, 6)
    build("Path", "path", 6, 6)
    job = clips.plan("tour")
    assert job["kind"] == "tour"
    stops = [s for s in job["shots"] if s.get("near")]
    assert len(stops) == 3  # the path isn't a stop
    first = db.q("SELECT id FROM habitat WHERE name='Old bench'")[0]["id"]
    assert stops[0]["near"]["id"] == first  # things with a story come first
    text = words(job)
    assert "This is my Old bench" in text and "first snowed" in text
    for s in stops:  # the camera looks at the thing, with Gino standing beside it
        it = db.q("SELECT x, y FROM habitat WHERE id=?", (s["near"]["id"],))[0]
        assert s["cam"]["around"] == [it["x"], it["y"]] and s["near"]["dist"] > 1


def test_a_tour_needs_a_few_things_to_show():
    build("Lantern", "lamp", 9, 3)
    assert clips.plan("tour")["kind"] == "cute"
    assert clips.plan("grow")["kind"] == "cute"


def test_watch_my_home_grow_starts_empty_and_counts_the_days():
    b = vitals.load()
    b["born"] = time.time() - 10 * 86400
    vitals.save(b)
    for i in range(6):
        build(f"thing {i}", "lamp", i * 2, 4)
    db.x("UPDATE habitat SET ts=? WHERE name='thing 0'", (time.time() - 9.5 * 86400,))
    job = clips.plan("grow")
    assert job["kind"] == "grow"
    ids = [r["id"] for r in db.q("SELECT id FROM habitat ORDER BY id")]
    assert [job["grow"]["order"][str(i)] for i in ids] == list(range(6))  # in the order he built them
    assert job["grow"]["labels"][0] == "Day 1" and job["grow"]["labels"][-1] == "Day 11"
    assert job["shots"][0]["grown"] == 0 and sum(1 for s in job["shots"] if s.get("grow")) == 1
    assert "6 things" in words(job)


def test_gino_can_choose_every_kind_of_video():
    schema = str(tools.CLIP_TOOL)
    for k in clips.KINDS:
        assert f"'{k}'" in schema
    for k in clips.KINDS:
        assert k in clips.KIND_NAMES


def test_three_at_once_are_three_different_stories(monkeypatch):
    for i in range(6):
        tools.run("build", {"name": f"thing {i}", "emoji": "🌼", "x": i, "y": 1, "kind": "bench"}, body())
    kinds = clips.pick_kinds(3)
    assert len(kinds) == 3 and len(set(kinds)) == 3
    assert clips.pick_kinds(3, "grow")[0] == "grow"  # dad's choice goes first


def test_three_at_once_are_filmed_one_after_another(monkeypatch):
    monkeypatch.setattr(clips, "available", lambda: True)
    filmed = []
    monkeypatch.setattr(clips, "_film", lambda cid, job: filmed.append(cid) or
                        db.x("UPDATE clips SET status='ready' WHERE id=?", (cid,)))
    monkeypatch.setattr(clips.threading, "Thread", lambda target, args, **k: type(
        "T", (), {"start": lambda self: target(*args)})())
    ids = clips.make_set(3)
    assert len(ids) == 3 and filmed == ids  # in order, never two at once
    rows = db.q("SELECT kind, made_by FROM clips ORDER BY id")
    assert len({r["kind"] for r in rows}) == 3 and all(r["made_by"] == "dad" for r in rows)


def test_a_set_waits_while_gino_is_still_filming(monkeypatch):
    monkeypatch.setattr(clips, "available", lambda: True)
    db.x("INSERT INTO clips(ts,kind,title,status) VALUES(?,?,?,?)", (time.time(), "day", "x", "making"))
    with pytest.raises(RuntimeError):
        clips.make_set(3)
    with pytest.raises(RuntimeError):
        clips.make("day")


def test_the_basic_look_is_still_there_for_a_slow_server():
    assert clips.LOOKS["basic"]["detail"] == "low" and clips.LOOKS["basic"]["film"] is None
    job = {"detail": "fur"}
    assert "unsharp" in clips._video_filter(job)[1] and "bt709" in clips._video_filter(job)[1]


def test_dads_page_says_what_a_video_is_waiting_for(monkeypatch, tmp_path):
    """"Waiting for the camera" says why: an old clip's finishing touch, a photo, or another video."""
    import threading
    from gino import photo, polish
    monkeypatch.setattr(clips, "CLIPS_DIR", tmp_path)
    seen = []

    class Render:  # stands in for the browser: notes what dad's page said, then fails quietly
        def __init__(self, *a, **k):
            seen.append(clips.progress.get(7))
            self.stdin = type("In", (), {"write": lambda s, b: None, "close": lambda s: None})()
            self.stderr, self.returncode = iter([]), 1

        def wait(self):
            return 1
    monkeypatch.setattr(clips.subprocess, "Popen", Render)
    db.x("INSERT OR REPLACE INTO clips(id, ts, kind, title, status) VALUES(7, ?, 'day', 'Day', 'making')", (time.time(),))
    polish._lock.acquire(); clips._busy.acquire()  # an old clip is being polished
    t = threading.Thread(target=clips._film, args=(7, {"kind": "day"}))
    t.start()
    for _ in range(200):
        if clips._waiting:
            break
        time.sleep(0.01)
    assert clips.camera_wanted()  # the polish sees this and steps aside
    assert "finishing touch" in clips.progress[7]
    clips._busy.release(); polish._lock.release()
    t.join(5)
    assert seen == ["setting up the camera (about a minute)"] and clips._waiting == 0
    db.x("DELETE FROM clips WHERE id=7")


def test_videos_cut_off_by_a_restart_are_filmed_again(monkeypatch, tmp_path):
    """An update or a `gino ...` setting restarts the server: the videos it cut off start again by themselves."""
    monkeypatch.setattr(clips, "available", lambda: True)
    monkeypatch.setattr(clips, "FILMING_MARK", tmp_path / "filming")
    filmed = []
    monkeypatch.setattr(clips, "_film", lambda cid, job: filmed.append((cid, job["kind"])) or
                        db.x("UPDATE clips SET status='ready' WHERE id=?", (cid,)))
    monkeypatch.setattr(clips.threading, "Thread", lambda target, args=(), **k: type(
        "T", (), {"start": lambda self: None})())
    ids = clips.make_set(3)  # the server restarts before any of them is filmed
    old = db.q("SELECT id FROM clips WHERE job=''")  # (rows from before this change can't be filmed again)
    assert not old
    tired = db.x("INSERT INTO clips(ts,kind,title,status,job,tries) VALUES(?,?,?,?,?,?)",
                 (time.time(), "day", "x", "making", '{"kind": "day"}', clips.MAX_TRIES))
    lost = db.x("INSERT INTO clips(ts,kind,title,status) VALUES(?,?,?,?)", (time.time(), "day", "x", "making"))
    monkeypatch.setattr(clips.threading, "Thread", lambda target, args=(), **k: type(
        "T", (), {"start": lambda self: target(*args)})())
    assert clips.resume(delay=0) == ids
    assert [cid for cid, _ in filmed] == ids  # all three, in order
    rows = {r["id"]: r for r in db.q("SELECT id, status, error, tries FROM clips")}
    assert all(rows[i]["status"] == "ready" and rows[i]["tries"] == 1 for i in ids)
    assert rows[tired]["status"] == "failed" and "too many" in rows[tired]["error"]
    assert rows[lost]["status"] == "failed"
    assert not (tmp_path / "filming").exists()  # the auto-update can go ahead again


def test_the_auto_update_waits_while_a_video_is_filming(monkeypatch, tmp_path):
    monkeypatch.setattr(clips, "available", lambda: True)
    monkeypatch.setattr(clips, "FILMING_MARK", tmp_path / "filming")
    marked = []
    monkeypatch.setattr(clips, "_film", lambda cid, job: marked.append((tmp_path / "filming").exists()) or
                        db.x("UPDATE clips SET status='ready' WHERE id=?", (cid,)))
    monkeypatch.setattr(clips.threading, "Thread", lambda target, args, **k: type(
        "T", (), {"start": lambda self: target(*args)})())
    clips.make_set(3)
    assert marked == [True, True, True] and not (tmp_path / "filming").exists()
    update = (clips.config.ROOT / "deploy" / "update.sh").read_text()
    assert "data/filming" in update


def test_the_filming_browser_never_touches_the_list():
    """The browser that films (and the polish) import this module too: that mustn't fail the videos being made."""
    import subprocess
    import sys
    cid = db.x("INSERT INTO clips(ts,kind,title,status) VALUES(?,?,?,?)", (time.time(), "day", "x", "making"))
    subprocess.run([sys.executable, "-c", "import gino.clips, gino.polish"], check=True, cwd=str(clips.config.ROOT),
                   env={**__import__("os").environ, "GINO_DATA_DIR": str(clips.config.DATA_DIR)})
    assert db.q("SELECT status FROM clips WHERE id=?", (cid,))[0]["status"] == "making"


def test_a_photo_never_waits_hours_for_the_camera(monkeypatch):
    """While videos film (three in a row can take hours on the small server), a photo for Bluesky gives up quickly.
    It used to wait for the camera inside Gino's turn, which froze his mind: no replies to dad, no turns."""
    from gino import photo, social
    monkeypatch.setattr(photo, "available", lambda: True)
    monkeypatch.setattr(photo, "WAIT_FOR_CAMERA", 0.05)
    monkeypatch.setattr(photo.subprocess, "run", lambda *a, **k: pytest.fail("no photo while the camera films"))
    photo._lock.acquire()  # a video is filming
    try:
        t0 = time.time()
        with pytest.raises(RuntimeError, match="busy filming"):
            photo.take("selfie")
        assert time.time() - t0 < 2
        monkeypatch.setattr(social, "configured", lambda: True)
        monkeypatch.setattr(social, "wait_minutes", lambda: 0)
        sent = []
        monkeypatch.setattr(social, "_send", lambda text, jpeg=b"", alt="": sent.append((text, jpeg)) or "at://x")
        monkeypatch.setattr(social.threading, "Thread", lambda target, args, **k: type(
            "T", (), {"start": lambda self: target(*args)})())
        said = social.post("A sunny afternoon by the lake.", "selfie", "Gino by the lake")
        assert said.startswith("Posting")  # the photo is taken in the background, his turn carries straight on
        assert sent == [("A sunny afternoon by the lake.", b"")]  # camera busy: the words still go up
        assert not social._photo_post["busy"]
    finally:
        photo._lock.release()


def test_filming_gives_way_to_gino_and_his_website(monkeypatch, tmp_path):
    """The browser and ffmpeg run at low priority, in their own group, so a stuck one can be stopped whole."""
    monkeypatch.setattr(clips, "CLIPS_DIR", tmp_path)
    started = []

    class Render:
        def __init__(self, cmd, **k):
            started.append((cmd, k))
            self.pid, self.returncode = 0, 1
            self.stdin = type("In", (), {"write": lambda s, b: None, "close": lambda s: None})()
            self.stderr = iter([])

        def wait(self):
            return 1
    monkeypatch.setattr(clips.subprocess, "Popen", Render)
    cid = db.x("INSERT INTO clips(ts,kind,title,status) VALUES(?,?,?,?)", (time.time(), "day", "x", "making"))
    clips._film(cid, {"kind": "day"})
    cmd, kw = started[0]
    assert cmd[:3] == ["nice", "-n", "10"] and "render" in cmd and kw["start_new_session"] is True
    assert config.CLIP_TIMEOUT >= 2 * 3600 or config.CLIP_LOOK == "basic"  # an HD video takes ~1 h on 2 processors


class FakeRender:
    """Stands in for the filming browser: prints frame lines (each after a pause), then ends with a return code."""
    def __init__(self, lines, pause=0.0, code=0, out=None):
        self.lines, self.pause, self.code, self.out = lines, pause, code, out
        self.pid, self.returncode, self.killed = 0, None, False
        self.stdin = type("In", (), {"write": lambda s, b: None, "close": lambda s: None})()

    @property
    def stderr(self):
        for line in self.lines:
            if self.killed:
                return
            time.sleep(self.pause)
            yield line.encode() + b"\n"
        if self.out and not self.killed:
            self.out.write_bytes(b"x" * 20_000)

    def wait(self):
        self.returncode = -9 if self.killed else self.code
        return self.returncode

    def kill(self):
        self.killed = True


def test_a_slow_video_is_left_to_finish_but_a_stuck_one_is_stopped(monkeypatch, tmp_path):
    """Filming in HD on the small server is slow. A video that keeps moving on is never cut off for being slow
    (that's what failed most videos with "it took too long"); one that stops moving on is stopped."""
    monkeypatch.setattr(clips, "CLIPS_DIR", tmp_path)
    monkeypatch.setattr(clips, "FILMING_MARK", tmp_path / "filming")
    monkeypatch.setattr(clips, "WATCH_EVERY", 0.02)
    monkeypatch.setattr(config, "CLIP_STALL", 0.3)
    monkeypatch.setattr(__import__("gino.tiktok").tiktok, "after_clip", lambda cid: None)
    from gino import polish
    monkeypatch.setattr(polish, "maybe_polish", lambda: None)
    monkeypatch.setattr(clips, "_stop", lambda p: p.kill())
    monkeypatch.setattr(config, "CLIP_TIMEOUT", 5)  # the very long overall limit isn't reached here
    slow = db.x("INSERT INTO clips(ts,kind,title,status) VALUES(?,?,?,?)", (time.time(), "day", "x", "making"))
    frames = [f"clip: frame {i}/10" for i in range(1, 11)]
    monkeypatch.setattr(clips.subprocess, "Popen", lambda *a, **k: FakeRender(
        frames, pause=0.1, out=tmp_path / f"gino-{slow}-day.mp4"))
    assert clips._film(slow, {"kind": "day"}) == "ok"  # 1 s in all, but never 0.3 s without a new frame
    assert db.q("SELECT status FROM clips WHERE id=?", (slow,))[0]["status"] == "ready"
    assert (tmp_path / "filming").exists()  # the mark was kept fresh, so the auto-update kept waiting

    stuck = db.x("INSERT INTO clips(ts,kind,title,status) VALUES(?,?,?,?)", (time.time(), "day", "x", "making"))
    monkeypatch.setattr(clips.subprocess, "Popen", lambda *a, **k: FakeRender(["clip: frame 1/10"] * 2, pause=1.0))
    assert clips._film(stuck, {"kind": "day"}) == "stuck"
    assert db.q("SELECT error FROM clips WHERE id=?", (stuck,))[0]["error"] == "the camera got stuck"


def test_running_out_of_memory_films_it_again_in_the_lighter_look(monkeypatch, tmp_path):
    """If Linux has to stop the HD filming for lack of memory, the same story is filmed again in 720p."""
    monkeypatch.setattr(clips, "available", lambda: True)
    monkeypatch.setattr(clips, "CLIPS_DIR", tmp_path)
    monkeypatch.setattr(clips, "FILMING_MARK", tmp_path / "filming")
    monkeypatch.setattr(__import__("gino.tiktok").tiktok, "after_clip", lambda cid: None)
    from gino import polish
    monkeypatch.setattr(polish, "maybe_polish", lambda: None)
    monkeypatch.setattr(clips, "_watch", lambda *a: None)  # (threads run straight away in this test)
    kills = iter([3, 4, 4, 4])  # one process stopped for lack of memory during the first (HD) try
    monkeypatch.setattr(clips, "_oom_kills", lambda: next(kills))
    jobs = []

    def render(cmd, **k):
        r = FakeRender(["clip: frame 1/1"], code=1)
        jobs.append(r)
        if len(jobs) == 2:
            r.code, r.out = 0, tmp_path / cmd[-1].rsplit("/", 1)[-1]
        return r
    seen = []
    monkeypatch.setattr(clips.subprocess, "Popen", render)
    real = clips._film
    monkeypatch.setattr(clips, "_film", lambda cid, job: seen.append(job["detail"]) or real(cid, job))
    monkeypatch.setattr(clips.threading, "Thread", lambda target, args=(), **k: type(
        "T", (), {"start": lambda self: target(*args)})())
    cid = clips.make("day", by="dad")
    assert seen == [clips.LOOKS["hd"]["detail"], "low"]
    row = db.q("SELECT status, tries, job FROM clips WHERE id=?", (cid,))[0]
    assert row["status"] == "ready" and row["tries"] == 2
    assert __import__("json").loads(row["job"])["width"] == 720


def test_gino_keeps_running_when_a_helper_runs_out_of_memory():
    """systemd's default restarts the whole of Gino when any of his processes is stopped for lack of memory: that
    restarted the server in the middle of filming. Gino's service must carry on instead."""
    unit = (config.ROOT / "deploy" / "systemd" / "gino.service").read_text()
    assert "OOMPolicy=continue" in unit
    update = (config.ROOT / "deploy" / "update.sh").read_text()
    assert update.index("pip\" install") < update.index("reset --quiet --hard \"$target\"")  # libraries first


def test_a_small_server_films_in_the_lighter_look_unless_dad_chooses():
    assert config._clip_look("auto", 0.9, 1) == "basic"  # Gino's 1 GB, 1-processor server
    assert config._clip_look("auto", 3.8, 2) == "hd"
    assert config._clip_look("hd", 0.9, 1) == "hd" and config._clip_look("basic", 8, 4) == "basic"
    job = clips.lighter({"kind": "day", "width": 1080, "height": 1920, "detail": "fur"})
    assert (job["width"], job["height"], job["detail"], job["kind"]) == (720, 1280, "low", "day")
