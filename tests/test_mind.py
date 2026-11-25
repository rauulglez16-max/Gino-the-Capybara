"""Gino's mind never makes dad wait long: streamed answers, a dead line noticed, dad's messages first."""
import json
import threading

import anthropic
import httpx2 as httpx  # the http library the Claude SDK uses
import pytest

from gino import brain, config, db, vitals


def _sse(blocks, stop="end_turn"):
    """A pretend Claude answer, sent bit by bit the way the real one is (server-sent events)."""
    ev = [("message_start", {"type": "message_start", "message": {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "content": [],
        "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 100, "output_tokens": 1}}})]
    for i, b in enumerate(blocks):
        if b["type"] == "text":
            ev += [("content_block_start", {"type": "content_block_start", "index": i,
                                            "content_block": {"type": "text", "text": ""}}),
                   ("content_block_delta", {"type": "content_block_delta", "index": i,
                                            "delta": {"type": "text_delta", "text": b["text"]}})]
        else:
            ev += [("content_block_start", {"type": "content_block_start", "index": i, "content_block": {
                       "type": "tool_use", "id": f"toolu_{i}", "name": b["name"], "input": {}}}),
                   ("content_block_delta", {"type": "content_block_delta", "index": i, "delta": {
                       "type": "input_json_delta", "partial_json": json.dumps(b["input"])}})]
        ev.append(("content_block_stop", {"type": "content_block_stop", "index": i}))
    ev += [("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                              "usage": {"output_tokens": 50}}),
           ("message_stop", {"type": "message_stop"})]
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in ev).encode()


@pytest.fixture
def claude(monkeypatch):
    """Point Gino's brain at a pretend Claude. Append answers to the list; requests are recorded."""
    answers, seen = [], []

    def handle(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=answers.pop(0), headers={"content-type": "text/event-stream"})
    monkeypatch.setattr(brain, "_client", anthropic.Anthropic(
        api_key="test", max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(handle))))
    monkeypatch.setattr(config, "FAKE_BRAIN", False)
    return answers, seen


def test_answers_are_streamed_and_read_in_full(claude):
    answers, seen = claude
    answers.append(_sse([{"type": "text", "text": "Hello dad!"}]))
    resp = brain.call(config.MODEL, [{"role": "user", "content": "hi"}], [], max_tokens=500)
    assert seen[0]["stream"] is True
    assert resp.content[0].text == "Hello dad!" and resp.stop_reason == "end_turn"
    assert resp.usage.output_tokens == 50


def test_a_dead_line_is_noticed_not_waited_on():
    brain._client = None
    try:
        t = brain.client().timeout
        assert t.read == brain.STALL_SECONDS <= 180 and t.connect <= 30
        assert brain.client().max_retries <= 2
    finally:
        brain._client = None


def test_turn_puts_its_thought_aside_when_dad_writes(claude):
    answers, seen = claude
    body = vitals.load()
    think = {"type": "tool_use", "name": "think", "input": {"thought": "what to build next..."}}
    answers += [_sse([think], stop="tool_use"), _sse([think], stop="tool_use")]
    real_run = brain.tools.run

    def dad_writes_meanwhile(name, a, b):
        brain._dad_waiting += 1  # dad pressed send while Gino was busy with this step
        return real_run(name, a, b)
    brain.tools.run = dad_writes_meanwhile
    try:
        out = brain.run_loop("turn", config.MODEL, "your turn", body, [])
    finally:
        brain.tools.run = real_run
        brain._dad_waiting = 0
    assert out.for_dad and len(seen) == 1  # stopped after the step it was on, no more paid steps
    assert body["thought"] == "what to build next..."  # what he already did still counts
    assert db.q("SELECT 1 FROM events WHERE text LIKE 'Dad wrote%'")


def test_dads_chat_goes_ahead_of_a_waiting_turn(claude):
    answers, _ = claude
    answers.append(_sse([{"type": "text", "text": "Hi dad! 🧡"}]))
    order = []
    brain.mind_lock.acquire()  # Gino is busy with something
    t = threading.Thread(target=lambda: order.append(brain.chat("hello son")))
    t.start()
    for _ in range(200):
        if brain.dad_is_waiting():
            break
        threading.Event().wait(0.01)
    assert brain.dad_is_waiting()
    brain.mind_lock.release()
    t.join(5)
    assert order == ["Hi dad! 🧡"] and not brain.dad_is_waiting()
    assert not brain.THINKING_MARK.exists()  # the auto-update can go ahead again


def test_a_broken_line_gets_a_kind_reply_not_an_error(claude):
    answers, _ = claude
    answers.append(b"event: error\ndata: {\"type\": \"error\", \"error\": {\"type\": \"overloaded_error\", "
                   b"\"message\": \"Overloaded\"}}\n\n")
    reply = brain.chat("are you there?")
    assert "lost my train of thought" in reply
    assert db.q("SELECT text FROM chat WHERE sender='gino'")[-1]["text"] == reply


def test_thinking_mark_is_there_only_while_he_thinks():
    assert not brain.THINKING_MARK.exists()
    with brain.thinking():
        assert brain.THINKING_MARK.exists() and brain.mind_lock.locked()
    assert not brain.THINKING_MARK.exists() and not brain.mind_lock.locked()
