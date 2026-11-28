import datetime as dt

from gino import config, vitals


def d(m, day):
    return dt.datetime(2026, m, day, 12, 0)


def test_looks_follow_the_calendar(monkeypatch):
    monkeypatch.setattr(config, "HEMISPHERE", "north")
    assert vitals.look(d(12, 1)) == "christmas"
    assert vitals.look(d(1, 6)) == "christmas"
    assert vitals.look(d(1, 7)) == "winter"
    assert vitals.look(d(3, 15)) == "spring"
    assert vitals.look(d(4, 10)) == "sakura"
    assert vitals.look(d(7, 1)) == "summer"
    assert vitals.look(d(10, 31)) == "autumn"
    assert vitals.look(d(11, 30)) == "autumn"


def test_south_gets_blossom_in_october(monkeypatch):
    monkeypatch.setattr(config, "HEMISPHERE", "south")
    assert vitals.look(d(10, 5)) == "sakura"
    assert vitals.look(d(4, 5)) == "autumn"
    assert vitals.look(d(12, 20)) == "christmas"


def test_weather_carries_the_look(monkeypatch):
    monkeypatch.setattr(config, "HEMISPHERE", "north")
    w = vitals.weather(d(12, 24))
    assert w["look"] == "christmas" and "Christmas" in w["text"]
    assert vitals.weather(d(7, 1))["look"] == "summer"
