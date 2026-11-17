"""The daily budget is a promise: these tests make sure a turn can't run past it."""
import time
from types import SimpleNamespace

import pytest

from gino import brain, budget, config, db, dreams, tools, vitals


def spend(usd: float):
    db.x("INSERT INTO spend(ts,day,purpose,model,input_tokens,output_tokens,cache_read,cache_write,usd) "
         "VALUES(?,?,?,?,?,?,?,?,?)", (time.time(), brain.local_now().strftime("%Y-%m-%d"), "test", "x", 0, 0, 0, 0, usd))


def test_no_step_when_budget_is_used_up():
    assert budget.step_allowance("claude-opus-5-5", 3.0, "turn", 10_000) == 0
    assert budget.step_allowance("claude-opus-5-5", 3.5, "turn", 10_000) == 0


def test_full_step_when_plenty_left():
    assert budget.step_allowance("claude-opus-5-5", 0.0, "turn", 10_000, web=True) == budget.MAX_STEP_TOKENS


def test_step_is_shortened_near_the_cap_and_never_overshoots():
    model, inp = "claude-opus-5-5", 20_000
    for spent in (2.5, 2.7, 2.8, 2.85, 2.9):
        n = budget.step_allowance(model, spent, "turn", inp, web=True)
        if n:
            assert spent + budget.worst_case_usd(model, inp, n, True) <= config.DAILY_BUDGET_USD + 1e-9
    assert 0 < budget.step_allowance(model, 2.75, "turn", inp) < budget.MAX_STEP_TOKENS


def test_chat_gets_one_and_a_half_times_the_budget():
    assert budget.step_allowance("claude-opus-5-5", 3.2, "chat", 10_000) > 0
    assert budget.step_allowance("claude-opus-5-5", 4.5, "chat", 10_000) == 0


class FakeClaude:
    """Pretends to be Claude: every step costs a known amount and asks for another tool."""

    def __init__(self, out_tokens=2000, in_tokens=30_000):
        self.calls, self.out, self.inp = [], out_tokens, in_tokens

    def __call__(self, model, messages, tool_list, max_tokens=16000):
        self.calls.append(max_tokens)
        n = len(self.calls)
        usage = SimpleNamespace(input_tokens=self.inp, output_tokens=min(self.out, max_tokens),
                                cache_read_input_tokens=0, cache_creation_input_tokens=0, server_tool_use=None)
        content = [SimpleNamespace(type="tool_use", id=f"t{n}", name="think", input={"thought": "hmm"})]
        return SimpleNamespace(usage=usage, model=model, content=content, stop_reason="tool_use")


@pytest.fixture
def real_brain(monkeypatch):
    monkeypatch.setattr(config, "FAKE_BRAIN", False)
    monkeypatch.setattr(config, "MAX_STEPS_PER_TICK", 60)
    fake = FakeClaude()
    monkeypatch.setattr(brain, "call", fake)
    return fake


def test_a_long_turn_stops_before_passing_the_cap(real_brain):
    spend(2.0)  # $1 left; each step costs about $0.16, so he gets a few steps and then must stop
    body = vitals.load()
    out = brain.run_loop("turn", "claude-opus-5-5", "go", body, tools.all_tools())
    assert out.out_of_budget
    assert 2 <= len(real_brain.calls) < 60
    assert brain.spent_today() <= config.DAILY_BUDGET_USD


def test_turn_is_skipped_when_not_even_one_step_fits(real_brain):
    spend(2.99)
    brain.take_turn()
    assert real_brain.calls == []
    assert "budget" in vitals.load()["activity"]


def test_chat_says_goodnight_instead_of_overspending(real_brain):
    spend(4.49)
    reply = brain.chat("hi")
    assert real_brain.calls == [] and "thought out" in reply


def test_dream_is_skipped_when_it_would_not_fit(real_brain, monkeypatch):
    spend(2.99)
    body = vitals.load()
    body["dream_due"], body["asleep_until"] = time.time() - 1, time.time() + 3600
    vitals.save(body)
    assert dreams.dream_now() is None
    assert real_brain.calls == []
    assert db.q("SELECT 1 FROM events WHERE text LIKE '%too deeply to dream%'")
