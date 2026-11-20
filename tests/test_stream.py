"""Gino's live TV: off by default, keys never leak, the picture only shows public things."""
import random

from fastapi.testclient import TestClient

from gino import config, db, stream


def test_off_until_a_key_is_given(monkeypatch):
    monkeypatch.setattr(config, "STREAM_YOUTUBE_KEY", "")
    monkeypatch.setattr(config, "STREAM_TIKTOK_KEY", "")
    assert stream.target("youtube") == "" and stream.target("tiktok") == ""


def test_keys_go_on_the_end_of_the_address_and_never_into_logs(monkeypatch):
    monkeypatch.setattr(config, "STREAM_YOUTUBE_KEY", "abcd-efgh-ijkl-mnop")
    assert stream.target("youtube") == "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"
    line = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop: Connection refused"
    assert "abcd" not in stream._redact(line)


def test_youtube_is_wide_and_tiktok_is_tall():
    assert stream.size("youtube") == (1280, 720)
    assert stream.size("tiktok") == (720, 1280)


def test_ffmpeg_sends_a_steady_stream(monkeypatch):
    monkeypatch.setattr(config, "FFMPEG", "/usr/bin/ffmpeg")
    cmd = stream.ffmpeg_cmd("youtube", "rtmp://example/live2/k")
    assert cmd[-3:] == ["-f", "flv", "rtmp://example/live2/k"]
    assert cmd[cmd.index("-g") + 1] == str(config.STREAM_FPS * 2)  # a keyframe every 2 seconds, as YouTube asks
    assert "loop.ffconcat" in " ".join(cmd) and "caption.png" in " ".join(cmd)


def test_scenes_follow_his_day_and_have_no_words():
    for asleep in (False, True):
        shots = stream._shots({"asleep": asleep, "weather": {"kind": "rain"},
                               "habitat": [{"x": 3, "y": 4, "kind": "pond"}]}, 23.9, random.Random(1))
        assert sum(s["dur"] for s in shots) == stream.SCENE_SECONDS
        assert all(s["captions"] == [] and s["weather"] == "rain" and s["asleep"] == asleep for s in shots)
        assert all(0 <= h < 24 for s in shots for h in s["hour"])


def test_playlist_loops_back_on_itself():
    d = stream.folder("youtube")
    for f in d.glob("*"):
        f.unlink()
    assert stream.write_playlist("youtube") is False  # nothing filmed yet
    for n in range(stream.KEEP_SCENES + 3):
        (d / f"scene-{1000 + n}.mp4").write_bytes(b"x")
    assert stream.write_playlist("youtube")
    body = (d / "loop.ffconcat").read_text().splitlines()
    assert body[-1] == "file 'loop.ffconcat'"
    assert len(body) == stream.KEEP_SCENES + 2 and "scene-1000.mp4" not in "".join(body)


def test_scene_job_is_public_only():
    db.x("INSERT INTO habitat(ts,name,emoji,x,y,description,kind) VALUES(?,?,?,?,?,?,?)",
         (0, "Raul's bench", "🪑", 3, 3, "for my dad Raul", "bench"))
    job = stream.scene_job("youtube", random.Random(2))
    text = str(job)
    assert "Raul" not in text and job["width"] == 1280 and job["title"] == ""


def test_the_tv_page_is_public_but_not_indexed():
    from gino.server import app
    r = TestClient(app).get("/stream")
    assert r.status_code == 200 and "Gino" in r.text
    assert r.headers["x-robots-tag"] == "noindex"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
