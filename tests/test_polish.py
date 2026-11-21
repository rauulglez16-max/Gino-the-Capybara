"""Who polishes Gino's videos (dad's PC, the server, or nobody) and what the server's own polish does."""
import shutil
import subprocess
import time

import pytest

from gino import clips, config, db, polish, tiktok


@pytest.fixture(autouse=True)
def fresh(monkeypatch, tmp_path):
    db.x("DELETE FROM clips")
    db.put("polisher_seen", 0)
    monkeypatch.setattr(clips, "CLIPS_DIR", tmp_path)
    monkeypatch.setattr(config, "CLIPS_ON", True)
    monkeypatch.setattr(config, "POLISHER", "pc")
    monkeypatch.setattr(clips, "ffmpeg", lambda: "ffmpeg")
    yield


def clip(tmp_path, age=0.0, **cols):
    n = db.q("SELECT COUNT(*) AS n FROM clips")[0]["n"]
    name = f"gino-{n}-day.mp4"
    (tmp_path / name).write_bytes(b"\0\0\0\x18ftypisom" + b"\0" * 20_000)
    names = ["ts", "kind", "title", "status", "filename", *cols]
    vals = [time.time() - age, "day", "A day in Gino's life", "ready", name, *cols.values()]
    return db.x(f"INSERT INTO clips({','.join(names)}) VALUES({','.join('?' * len(names))})", tuple(vals))


def test_pc_mode_leaves_fresh_clips_to_filmcraft_while_the_pc_is_on(tmp_path):
    new, old = clip(tmp_path), clip(tmp_path, age=polish.PC_GRACE + 60)
    assert polish.due() == [new, old]  # PC off: the server does them all
    assert {c["id"] for c in clips.polish_queue()} == {new, old}  # the PC asking marks it as on
    assert polish.due() == [old]  # PC on: the server only takes what FilmCraft hasn't done in time


def test_server_mode_polishes_straight_away_and_the_pc_gets_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "POLISHER", "server")
    cid = clip(tmp_path)
    assert clips.polish_queue() == []
    assert polish.due() == [cid]  # even though the PC just asked


def test_off_means_nobody_polishes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "POLISHER", "off")
    clip(tmp_path)
    assert clips.polish_queue() == [] and polish.due() == []


def test_clips_on_tiktok_already_polished_or_failed_are_left_alone(tmp_path):
    clip(tmp_path, tiktok_status="sent")
    clip(tmp_path, polished="x.mp4")
    clip(tmp_path, polish_note="server failed")
    clip(tmp_path, age=5 * 86400)
    assert polish.due() == []


def test_the_server_polish_is_saved_and_filmcraft_can_still_replace_it(tmp_path, monkeypatch):
    cid = clip(tmp_path)

    def fake_run(cmd, **kw):  # stands in for ffmpeg: writes the finished video
        open(cmd[-1], "wb").write(b"\0\0\0\x18ftypisom" + b"\2" * 30_000)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")
    monkeypatch.setattr(polish.subprocess, "run", fake_run)
    monkeypatch.setattr(polish.threading, "Thread", lambda target, args, **k: type(
        "T", (), {"start": lambda self: target(*args)})())
    assert polish.maybe_polish() == cid
    row = clips.listing()[0]
    assert row["polished"] and row["polished_by"] == "server" and not row["polishing"]
    server_file = clips.path(cid)
    assert server_file.name.endswith("-finished.mp4")
    clips.save_polished(cid, b"\0\0\0\x18ftypisom" + b"\3" * 30_000)  # FilmCraft finishes later: its version wins
    assert clips.listing()[0]["polished_by"] == "pc" and not server_file.exists()
    assert polish.maybe_polish() is None  # nothing left to do


def test_a_failed_server_polish_isnt_tried_again_and_again(tmp_path, monkeypatch):
    cid = clip(tmp_path)
    monkeypatch.setattr(polish.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, b"", b"boom"))
    monkeypatch.setattr(polish.threading, "Thread", lambda target, args, **k: type(
        "T", (), {"start": lambda self: target(*args)})())
    polish.maybe_polish()
    assert db.q("SELECT polish_note FROM clips WHERE id=?", (cid,))[0]["polish_note"] == "server failed"
    assert polish.due() == []


def test_the_daily_tiktok_video_waits_for_its_polish_unless_polishing_is_off(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TIKTOK_AUTO", True)
    monkeypatch.setattr(tiktok, "connected", lambda: True)
    sent, waited = [], []
    monkeypatch.setattr(tiktok, "_auto_send", lambda cid: sent.append(cid))
    monkeypatch.setattr(tiktok.threading, "Thread", lambda target, args, **k: type(
        "T", (), {"start": lambda self: waited.append(args[0])})())
    cid = clip(tmp_path)
    tiktok.after_clip(cid)  # PC off, but the server will polish it
    assert waited == [cid] and sent == []
    monkeypatch.setattr(config, "POLISHER", "off")
    tiktok.after_clip(cid)
    assert sent == [cid]


def test_the_narrator_reads_words_not_emoji_and_never_talks_over_itself():
    assert polish.speakable("Heave-ho! 💪") == "Heave-ho!"
    assert polish.speakable("“It came out just like the dream…” #capybara") == "It came out just like the dream."
    assert polish.speakable("🌙✨") == ""
    lines = [{"at": 0.2}, {"at": 0.5}, {"at": 10}, {"at": 19.5}]
    starts = polish.timing(lines, [2.0, 1.0, 1.0, 1.0], seconds=20)
    assert starts[0] == pytest.approx(0.35) and starts[1] >= starts[0] + 2.0  # waits for the line before
    assert starts[2] == pytest.approx(10.15) and starts[3] is None  # too close to the end: skipped


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_the_server_polish_makes_a_tall_1080p_video(tmp_path):
    src, out = tmp_path / "in.mp4", tmp_path / "out.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=720x1280:r=24:d=1.5",
                    "-f", "lavfi", "-i", "sine=f=330:d=1.5", "-shortest", "-pix_fmt", "yuv420p", str(src)], check=True)
    polish.make(str(src), str(out), {"lines": [{"text": "Hello! 👋", "at": 0.1}]}, voice="")
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(out)], capture_output=True, text=True)
    assert p.stdout.strip() == "1080,1920"
