"""The money guard: makes sure no single thought can push Gino past his daily budget.

Gino thinks in "steps": each step is one paid call to Claude. A turn can have several steps (look around, use a
tool, look at the result, use another tool...). Before every step we work out the most that step could cost,
and only let it happen if it fits in what's left of today's budget. If only a little money is left, the step is
allowed a shorter answer; if not even a short step fits, Gino stops thinking for the day.

How the worst case is worked out (on purpose, it's pessimistic):
- everything he reads is priced as if nothing were cached (cache writes, the dearest kind of input),
- if he has the web tools, we assume he uses all his searches and reads the biggest pages allowed,
- his answer is capped with max_tokens, so its cost is known in advance.
"""
import json

from . import config

MAX_STEP_TOKENS = 16000  # the longest answer (thinking included) one step may give
MIN_STEP_TOKENS = 1500  # below this a step is too short to be useful, so we stop instead
CHARS_PER_TOKEN = 3.0  # rough and on the generous side (real text is nearer 4 characters a token)
CACHE_WRITE = 1.25  # cache writes cost 1.25x normal input
# What the web tools can add inside one step: 3 searches (~3k tokens of results each, $0.01 each) and
# 3 page reads (up to 8k tokens each). Kept in step with tools.SERVER_TOOLS.
WEB_SEARCHES = 3
WEB_INPUT_TOKENS = 3 * 3000 + 3 * 8000


def cap(purpose: str) -> float:
    """Today's limit for this kind of thinking. Chatting with dad may go up to 1.5x, so he can always say hi."""
    return config.DAILY_BUDGET_USD * (1.5 if purpose == "chat" else 1.0)


def prices(model: str) -> tuple[float, float, float]:
    return config.PRICES.get(model) or config.PRICES.get(config.MODEL) or (5.0, 25.0, 0.5)


def estimate_tokens(*parts) -> int:
    """A generous guess at how many tokens some text, messages or tool definitions take."""
    n = 0
    for p in parts:
        n += len(p) if isinstance(p, str) else len(json.dumps(p, default=str))
    return int(n / CHARS_PER_TOKEN) + 1


def uses_web(tool_list: list) -> bool:
    return any(str(t.get("type", "")).startswith(("web_search", "web_fetch")) for t in tool_list or [])


def worst_case_usd(model: str, input_tokens: int, max_tokens: int, web: bool) -> float:
    pin, pout, _ = prices(model)
    tokens_in = input_tokens + (WEB_INPUT_TOKENS if web else 0)
    usd = (tokens_in * pin * CACHE_WRITE + max_tokens * pout) / 1e6
    return usd + (WEB_SEARCHES * config.WEB_SEARCH_USD if web else 0)


def step_allowance(model: str, spent: float, purpose: str, input_tokens: int, web: bool = False,
                   want: int = MAX_STEP_TOKENS) -> int:
    """How long an answer the next step may give (max_tokens), or 0 if no useful step fits in the budget."""
    left = cap(purpose) - spent
    if left <= 0:
        return 0
    pout = prices(model)[1]
    room = left - worst_case_usd(model, input_tokens, 0, web)
    allowed = int(room * 1e6 / pout) if room > 0 else 0
    allowed = min(want, allowed)
    return allowed if allowed >= min(MIN_STEP_TOKENS, want) else 0
