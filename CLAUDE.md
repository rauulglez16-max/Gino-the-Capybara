# Notes for anyone (human or Claude) changing Gino

## Always add a moment to Gino's story timeline

Gino's public website has a timeline of his life at `/timeline` ("His story so far"). It is built from
`gino/timeline.json`, so **every pull request that gives Gino something new (a feature, a new look, a new place to
visit) must add one entry to the end of `gino/timeline.json` in the same pull request.** Small fixes that nobody
would notice don't need one; fold them into the entry they belong to instead.

An entry looks like this:

```json
{
  "date": "2026-11-17",
  "emoji": "🌙",
  "title": "Gino starts dreaming",
  "text": "When he sleeps, his days now mix into dreams made from his own memories...",
  "link": "/live",
  "pr": 15
}
```

- `date`: the day the change goes live (YYYY-MM-DD). Entries stay in date order, oldest first.
- `emoji`, `title`, `text`: required. Write for visitors: short, warm, plain English, no technical words
  (no "API", "endpoint", "PR", file names). Talk about Gino, not about the code.
- `link`: optional, a page on his site to go and see it (`/live`, `/blog`, `/blog/shop`, `/`) or an `https://` link.
- `pr`: optional, the pull request number (the page shows a small "how it was built" link to it). If you don't know the
  number yet, add the entry without it, then add it once the pull request exists.
- **Privacy:** this page is public. Never mention Gino's family, the owner, chats, money, server details, passwords or
  anything else from the private page. Same rule as his blog (see `gino/public.py`).

`tests/test_timeline.py` checks the file is valid (`python -m pytest tests/test_timeline.py`). The page picks up the
new entry by itself once it's deployed; no code changes are needed.
