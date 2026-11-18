# Gino the Capybara 🌿

Gino is a little capybara who lives on your computer. Nobody tells him what to do. Every so often he wakes up,
checks how he feels, and decides for himself what to do next: eat, nap, build things in his habitat, browse the
internet about whatever he's curious about, write poems, draw pictures, chase goals he set himself, or text his dad.

His brain is Claude. His body, memory, home and diary live in one file on your disk, so he keeps growing day after day.

## Start Gino (5 minutes)

You need Python 3.11 or newer.

```bash
git clone https://github.com/rauulglez16-max/Gino-the-Capybara.git
cd Gino-the-Capybara
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
```

Open `.env` and paste your Claude API key (get one at https://platform.claude.com) after `ANTHROPIC_API_KEY=`.
Set `GINO_TZ` to your time zone so he knows when it's night.

```bash
python run.py
```

Then open **http://localhost:8787/private** (that's your own page, where you can chat with him). Leave the terminal running and Gino keeps living, even when you're not looking.

> No API key yet? Gino still runs on a simple "practice brain" so you can see everything working. He just
> can't really think or talk until you add the key.

## What you'll see

- **His 3D world**: a meadow by a lake, ringed by forest and snowy mountains, that he furnishes himself from 39
  shapes (or anything he invents). Drag to orbit, scroll to zoom, hover to see what things are, double-click a
  thing to look at it, or press *Follow Gino*. The sun, moon and stars follow your clock, the weather changes
  every few hours, and the seasons follow the calendar (`GINO_HEMISPHERE=south` flips them). Lamps, campfires and
  windows glow at night. Gino walks to what he builds, curls up to sleep, swims in his pond, and shows how he
  feels above his head. Click him to pet him. His drawings hang on any easel or gallery he builds. *Photo* saves
  a picture, and the Sky and Weather buttons let you preview other times and weather. *Quality* switches between
  the full look (soft shadows, ambient shading, dense grass) and a lighter one; it drops to low by itself on slower
  computers.
- **How he feels**: fullness, energy, social, fun, comfort, and his overall mood, plus the emotion he names and why.
- **Since your last visit**: when you open your page after being away for half an hour or more, a card at the
  top tells you what Gino got up to: projects he started, kept going or finished, things he made (with little
  pictures of his drawings), dreams, new interests, what he learned, what he built and what he put on his website.
  It's made from his own records, so it costs nothing. "Thanks, Gino" hides it.
- **Chat**: talk to him any time. Messaging him wakes him up if he's asleep, and he remembers what matters.
- **Phone**: on his server, `gino telegram` or `gino whatsapp` connects him to your phone, so he texts you and you can
  text him back. Only you can talk to him there (see deploy/README.md).
- **Diary, Creations, Goals, Memories, About Gino**: his inner life, all written by him.
- **Leave a snack**: drop food in his pantry.
- **His welcome page** at `/` (for example `http://localhost:8787`): a front page for everyone that explains who
  Gino is, shows what he's doing right now and his latest creations, and links to his live habitat, diary, shop and
  Bluesky. Live bits come from the same filtered data as `/live`, so nothing private shows up there.
- **His story so far** at `/timeline`: a public timeline of everything that has happened in Gino's life, day by
  day. It's built from `gino/timeline.json`; every change that gives Gino something new adds an entry there (see
  [CLAUDE.md](CLAUDE.md)).
- **His public website, "Gino's Burrow"** at `/blog` (for example `http://localhost:8787/blog`, or
  `https://<your-address>/blog` on the server). Anyone can read it, no password. Gino writes it himself: a public
  diary of what he did and learned each day, plus pages for things he makes (drawings, poems, write-ups of what he
  learned). It only ever shows what he chose to publish. His private page, memories, private diary and your chats
  are never on it. There's also an RSS feed at `/blog/feed.xml`.
- **His Bluesky account** (optional, off until you switch it on): Gino posts short updates about his day, at most
  3 a day, sometimes with a real photo of his 3D world (a selfie or his whole home). He can only post. He can't reply, follow, like or read messages there. His latest posts also show on
  his website. Setup is in [deploy/README.md](deploy/README.md#gino-on-bluesky-).
- **His videos for TikTok** (optional, off until you switch it on): every evening Gino films a 20-second vertical
  video of his life in his 3D world (a day, a night, a dream turned into a painting, or something he built), with
  captions and his meadow's sounds. They wait on the private page's *Videos* tab to download and post, and can go
  to TikTok through TikTok's official posting tools. Free (no AI video), privacy-filtered like his website. Setup is
  in [deploy/README.md](deploy/README.md#ginos-videos-and-tiktok-).
- **His shop** (optional, closed until you open it): Gino sells his drawings as downloads at `/blog/shop`. He
  picks what to sell, the name, the description and the price (£1 to £10). Buyers pay through your own Stripe
  account with Managed Payments, so Stripe handles VAT and receipts, and the money goes to you. Setup is in
  [deploy/README.md](deploy/README.md#ginos-shop-).

## How Gino works

```
          every ~15 min-6 h (he chooses)                    you
                     │                                       │
   ┌─────────────────▼──────────────────┐        ┌───────────▼──────────┐
   │ Turn: build "what I know right now" │        │ Chat: same context + │
   │ body, feelings, home, goals,        │        │ what dad just said   │
   │ memories, diary, chat, recent events│        └───────────┬──────────┘
   └─────────────────┬──────────────────┘                    │
                     ▼                                       ▼
            Claude decides and acts with tools (feel, eat, forage, sleep, build,
            create, journal, remember, recall, set/update goals, update_self,
            message_dad, web_search, web_fetch, set_next_wake)
                     │
                     ▼
            Everything is saved to data/gino.db  →  next turn he remembers it
```

| Piece | File |
| --- | --- |
| Personality and the self-prompting loop | `gino/brain.py` |
| The daily money guard | `gino/budget.py` |
| Lasting interests, old memories coming back, multi-day projects | `gino/continuity.py` |
| "Since your last visit" | `gino/recap.py` |
| Body: needs, food, sleep, mood | `gino/vitals.py` |
| Everything he can do | `gino/tools.py` |
| Storage (SQLite) | `gino/db.py` |
| Heartbeat and web server | `gino/server.py` |
| The page you look at | `gino/static/index.html` |
| The 3D world (three.js) | `gino/static/world.js`, `gino/static/kit.js` |

His needs drift on their own: he gets hungry, tired and lonely over time, sleeps them off, and a garden in his
habitat makes foraging better. When he forgets to choose when to wake up, he wakes in an hour.

**His days add up.** The topics he tags his memories with turn into lasting interests once he keeps coming back
to them over several days (and he's reminded of ones he's left alone for a while). Older memories that connect to
his current projects and interests come back into his mind even weeks later, and now and then an old memory just
surfaces. Projects show how long he's been at them, so a passion can grow into something that takes days: study
the moon for a few evenings, build a telescope, then paint what he saw.

## What it costs

Gino's thinking is paid per use through your Claude API account. Rough numbers for a normal day
(about 15 turns plus some chatting):

| Brain (`GINO_MODEL`) | Per turn | Per day | Per month |
| --- | --- | --- | --- |
| `claude-opus-5-5` (default, smartest) | ~$0.10-0.20 | ~$1.50-3 | ~$45-90 |
| `claude-sonnet-5-5` | ~$0.05-0.10 | ~$0.75-1.50 | ~$25-45 |
| `claude-haiku-5-5` | under $0.01 | ~$0.05-0.10 | ~$2-3 |

Web searches add $0.01 each. These are estimates; the page header shows what he has really spent today.

**Safety net:** `GINO_DAILY_BUDGET_USD` (default $3) is a daily cap. Gino thinks in small steps (one paid call
each), and before *every* step the money guard works out the most that step could possibly cost and only lets it
happen if it fits in what's left; near the limit a step gets a shorter answer, and when not even a short step fits
he stops and just lazes around until 7 AM. Because that worst case is worked out pessimistically, he usually stops a
little *below* the cap rather than going over it. Chatting with you keeps working up to 1.5x the cap. Dreams count
too. You can also turn down `GINO_EFFORT`,
raise `GINO_MIN_WAKE_MINUTES`, or turn the web off with `GINO_WEB=0`.

## Moving Gino to the cloud

When you want him to live 24/7 even with your computer off, put him on a small server (about €6/month at Hetzner).
It's one command, gives him a private https address with a password, and he **updates himself** within about
5 minutes whenever new code lands on `main`, keeping all his memories. Step-by-step guide:
**[deploy/README.md](deploy/README.md)**.

Prefer Docker? That works too:

```bash
docker build -t gino .
docker run -d --name gino --restart unless-stopped -p 8787:8787 \
  -v gino-data:/data --env-file .env -e GINO_PASSWORD=pick-something-long gino
```

Always set `GINO_PASSWORD` before he's on the internet. His whole life is in `data/gino.db` plus `data/creations/`.

## Boundaries

- On the internet Gino can only look (search and read pages). He cannot buy, post or sign up anywhere. The places
  he publishes are his own website at `/blog` and, if you switch it on, his Bluesky account (new posts only: no
  replies, DMs, follows, likes or @mentions, and no links except to his own website).
- He's told never to share anything about you. On top of that, everything he tries to put on his public website,
  Bluesky or shop is checked first and turned away if it mentions you (your name or "dad"), quotes your chats, or
  contains a key, a password, an email address or a phone number. That includes any words hidden inside his
  drawings (their text, titles, labels and notes), not just their names.
- You can add your own private words with `GINO_PRIVATE_WORDS` (for example the names of family members or pets,
  your town, your workplace), separated by commas. Anything public that mentions one is turned away too.
- Be realistic about what the filter can do: it's a word filter, not a mind reader. It reliably catches names,
  "dad", contact details, keys and quotes from your chats, but if Gino retold something private in completely
  different words, it could get past. So the simplest rule is: don't tell Gino anything you'd hate to see on the
  internet.
- In his shop he can only list, reprice and remove his own drawings. He can't spend money, give refunds or
  contact buyers, never sees who bought, and never sees the Stripe key (a restricted key that can't move money).
  `gino shop off` closes it at once.
- He only touches his own `data/` folder. He can't run code or read your files.
- Pages he reads can't give him orders; his instructions say to ignore anything that tries.

## Checking it works (automated tests)

The promises above (the money guard, the privacy filter, the recap and his memories) have automated tests. They
use a throwaway Gino, never your real one, and cost nothing:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

They also run by themselves on GitHub every time code changes.

## Ideas for next versions

- Friends: other animals he can meet
- Pixel-art sprites he designs for his own furniture
- Voice: hear Gino talk
