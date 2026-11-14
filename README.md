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

Then open **http://localhost:8787**. Leave the terminal running and Gino keeps living, even when you're not looking.

> No API key yet? Gino still runs on a simple "practice brain" so you can see everything working. He just
> can't really think or talk until you add the key.

## What you'll see

- **His 3D world**, a meadow ringed by hills and forest that he furnishes himself. Drag to orbit, scroll to zoom,
  hover over things to see what they are, or press *Follow Gino*. The sun, moon and stars follow your clock;
  lamps and campfires glow at night. He walks to what he builds, curls up to sleep, and swims in his pond.
- **How he feels**: fullness, energy, social, fun, comfort, and his overall mood, plus the emotion he names and why.
- **Chat**: talk to him any time. Messaging him wakes him up if he's asleep, and he remembers what matters.
- **Diary, Creations, Goals, Memories, About Gino**: his inner life, all written by him.
- **Leave a snack**: drop food in his pantry.

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
| Body: needs, food, sleep, mood | `gino/vitals.py` |
| Everything he can do | `gino/tools.py` |
| Storage (SQLite) | `gino/db.py` |
| Heartbeat and web server | `gino/server.py` |
| The page you look at | `gino/static/index.html` |
| The 3D world (three.js) | `gino/static/world.js` |

His needs drift on their own: he gets hungry, tired and lonely over time, sleeps them off, and a garden in his
habitat makes foraging better. When he forgets to choose when to wake up, he wakes in an hour.

## What it costs

Gino's thinking is paid per use through your Claude API account. Rough numbers for a normal day
(about 15 turns plus some chatting):

| Brain (`GINO_MODEL`) | Per turn | Per day | Per month |
| --- | --- | --- | --- |
| `claude-opus-5-5` (default, smartest) | ~$0.10-0.20 | ~$1.50-3 | ~$45-90 |
| `claude-sonnet-5-5` | ~$0.05-0.10 | ~$0.75-1.50 | ~$25-45 |
| `claude-haiku-5-5` | under $0.01 | ~$0.05-0.10 | ~$2-3 |

Web searches add $0.01 each. These are estimates; the page header shows what he has really spent today.

**Safety net:** `GINO_DAILY_BUDGET_USD` (default $3) is a hard daily cap. When he reaches it he stops thinking and
just lazes around until 7 AM. Chatting keeps working up to 1.5x the cap. You can also turn down `GINO_EFFORT`,
raise `GINO_MIN_WAKE_MINUTES`, or turn the web off with `GINO_WEB=0`.

## Moving Gino to the cloud (later)

When you want him to live 24/7 even with your computer off, put him on a small server (about $5/month, for example
Hetzner, DigitalOcean or Fly.io) with Docker:

```bash
docker build -t gino .
docker run -d --name gino --restart unless-stopped -p 8787:8787 \
  -v gino-data:/data --env-file .env -e GINO_PASSWORD=pick-something-long gino
```

Always set `GINO_PASSWORD` before he's on the internet. To bring his memories along, copy your local `data/` folder
into the volume first: his whole life is in `data/gino.db` plus `data/creations/`.

## Boundaries

- On the internet Gino can only look (search and read pages). He has no accounts and cannot buy, post or sign up.
- He's told never to share anything about you.
- He only touches his own `data/` folder. He can't run code or read your files.
- Pages he reads can't give him orders; his instructions say to ignore anything that tries.

## Ideas for next versions

- Phone notifications when Gino messages you
- Weather and seasons in his world
- Friends: other animals he can meet
- Pixel-art sprites he designs for his own furniture
- Voice: hear Gino talk
