"""Dad petting Gino or leaving food never waits for Gino to finish a thought (that used to freeze the website)."""
import time

from fastapi.testclient import TestClient

from gino import brain, db, server, vitals


def test_pet_and_gift_dont_wait_while_gino_thinks():
    client = TestClient(server.app)
    social = vitals.load()["social"]
    brain.mind_lock.acquire()  # Gino is in the middle of a long turn
    try:
        started = time.time()
        for _ in range(3):
            assert client.post("/api/pet").json() == {"ok": True}
        assert client.post("/api/gift", json={"food": "melon"}).json() == {"ok": True}
        assert time.time() - started < 5  # answered straight away, not after the turn
        assert vitals.load()["social"] == social  # written down, not felt yet
    finally:
        brain.mind_lock.release()
    with brain.mind_lock:  # his mind is free again: he gets them
        body = vitals.settle(vitals.load())
    assert body["pantry"].get("melon", 0) >= 1
    assert body["social"] == min(100, social + 3 + 4)  # the gift, plus one pet (pets count once every 10 minutes)
    assert len(db.q("SELECT 1 FROM events WHERE kind='pet'")) == 1
    assert vitals.settle(dict(body)) == body  # nothing left over


def test_pet_is_felt_at_once_when_gino_is_free():
    client = TestClient(server.app)
    social = vitals.load()["social"]
    client.post("/api/pet")
    assert vitals.load()["social"] == min(100, social + 4)
