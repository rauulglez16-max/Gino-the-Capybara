# Give Gino a home in the cloud ☁️🌿

This puts Gino on a small server that's on day and night, so he keeps living with your computer off.
You'll need about 20 minutes, a card for Hetzner, and your Claude API key.

When you're done:

- Gino lives at a private web address with a padlock, like `https://203-0-113-7.sslip.io`, behind a password.
- His public website, which he writes himself, is the same address plus `/blog`, like
  `https://203-0-113-7.sslip.io/blog`. Anyone can read that one, no password. `gino status` shows both addresses.
- **He updates himself.** Every 5 minutes the server checks GitHub. When new code lands on `main`, it saves a
  backup of Gino, switches to the new code and restarts him. His memories, diary, home and creations stay put.
- If a new version is broken and won't start, the server goes back to the version that worked and leaves the broken
  one alone until something newer arrives. Gino doesn't get stuck offline.
- It keeps a backup of his memories every day (the newest 20 are kept).

**Cost:** the server is about €6/month plus VAT (~£6). Gino's thinking is billed separately by your Claude
account, exactly as on your computer (see the main README; the daily cap still applies).

---

## Step 1: Rent a server at Hetzner (10 minutes)

1. Sign up at **https://console.hetzner.com** and verify your account. Hetzner sometimes asks new customers for ID
   or a small prepayment; that's normal.
2. Create a **Project** (call it `Gino`), then click **Create Server** and choose:
   - **Location:** Nuremberg or Falkenstein (Germany) or Helsinki. Any is fine; they're all close to London.
   - **Image:** **Ubuntu 24.04**.
   - **Type:** **Shared vCPU, Cost-Optimized → CX23** (x86, 2 vCPU, 4 GB). If it says *unavailable*, try another
     location, or pick **CAX11** (Arm, same size, works just as well) or **CPX02**. Gino is tiny; any of these is plenty.
   - **Networking:** keep **Public IPv4** ticked (it's €0.50/month and you need it).
   - **SSH keys:** skip it. Hetzner will email you a root password instead.
   - Leave everything else as it is, give it a name like `gino`, and click **Create & Buy now**.
3. After a minute you'll see the server's **IP address** (four numbers like `203.0.113.7`) and get an email with
   the **root password**.

## Step 2: Log in to the server (2 minutes)

Open a terminal on your computer:

- **Mac:** press `Cmd + Space`, type `Terminal`, press Enter.
- **Windows:** press the Windows key, type `PowerShell`, press Enter.

Type this, with your server's IP address, and press Enter:

```bash
ssh root@203.0.113.7
```

- It asks *"Are you sure you want to continue connecting?"* Type `yes` and press Enter.
- It asks for the password: paste the one from the email (nothing shows while you type or paste, that's normal),
  press Enter.
- The first time, it asks you to choose a **new** root password: paste the old one once more, then type a new one
  twice. Keep it somewhere safe.

You're in when the line starts with `root@gino:~#`.

## Step 3: Paste the one command (3 minutes)

```bash
curl -fsSL https://raw.githubusercontent.com/rauulglez16-max/Gino-the-Capybara/main/deploy/install.sh | bash
```

It installs everything, then asks for your Claude API key: paste it and press Enter (or press Enter to skip and
add it later with `gino set-key`). At the end it prints something like:

```
🌿 Gino is home! 🎉

   Visit him:   https://203-0-113-7.sslip.io
   Password:    k7mq2xv9pa4tn8rb   (write this down; see it again any time with: gino password)
```

Open that address in your browser, type the password when Gino asks, and say hi. 🐾
The padlock address can take a minute or two to start working the very first time.

You can close the terminal now. Gino keeps living.

---

## Bringing Gino's memories from your computer

If Gino already lived on your computer, you can move his whole life over. On **your computer**, in a terminal,
go to the Gino folder (where `run.py` is), stop Gino there (Ctrl+C), and run, with your IP:

```bash
scp -r data/gino.db data/creations root@203.0.113.7:/tmp/
```

Then log in to the server (`ssh root@203.0.113.7`) and run:

```bash
gino stop && gino backup
cp /tmp/gino.db /opt/gino/data/ && cp -r /tmp/creations/. /opt/gino/data/creations/
rm -f /opt/gino/data/gino.db-wal /opt/gino/data/gino.db-shm
chown -R gino:gino /opt/gino/data && gino start
```

From then on, visit him at the server address only. Two Ginos with the same memories would drift apart.

## Let Gino text your phone 📱

Gino can message you on **Telegram**, and you can text him back from anywhere. It's free. Only you can talk to
him there: the bot is locked to your phone, and anyone else who finds it gets no answer at all.

1. Install **Telegram** on your phone (App Store / Google Play) and sign up, if you haven't already.
2. In Telegram, search for **@BotFather** (the one with the blue tick) and open it. Send `/newbot`.
   - It asks for a name: type `Gino`.
   - It asks for a username that ends in `bot`, like `GinoTheCapybara_bot`. If it's taken, add some numbers.
   - It replies with a **token**, a long line like `8123456789:AAH4k...`. Copy it. Keep it secret: it's the bot's password.
3. On your computer, open PowerShell and log in to the server: `ssh root@<your IP>`
4. Type this and press Enter:

   ```bash
   gino telegram
   ```

   Paste the token (in PowerShell, right-click pastes) and press Enter.
5. It says *"Now open Telegram..."*. On your phone, search for your bot's username, open it, tap **Start**.
6. A couple of seconds later the server says **Done!** and your phone gets a *"Connected!"* message. That's it. 🎉

From now on, when Gino uses his "message dad" ability, it pops up on your phone (silently between 11pm and 7am),
and whatever you text the bot reaches him, just like chatting on his page. Both show up in the same chat history.

| Command | What it does |
| --- | --- |
| `gino telegram test` | Send a test message to your phone |
| `gino telegram` | Connect again (new phone, new bot, or a new token) |
| `gino telegram off` | Disconnect his phone line |

If you ever think someone saw the token, open @BotFather, send `/revoke`, pick your bot, and run
`gino telegram` again with the new token.

## Looking after Gino

Log in with `ssh root@<your IP>` and type `gino` to see everything:

| Command | What it does |
| --- | --- |
| `gino status` | Is he running, which version, which brain |
| `gino logs` | What happened recently (including updates) |
| `gino restart` | Restart him |
| `gino update` | Check GitHub for new code right now instead of waiting 5 minutes |
| `gino backup` | Save a copy of his memories now |
| `gino password` | Show the page password (`gino password NEW` changes it) |
| `gino set-key` | Give him a new Claude API key |
| `gino telegram` | Connect him to your phone (see above) |
| `gino settings` | Change any setting (model, budget, time zone...). Save with Ctrl+O, Enter, then Ctrl+X |

## Where things live on the server

| What | Where |
| --- | --- |
| Gino's memories, diary, home, creations | `/opt/gino/data/` (never touched by updates) |
| Backups | `/opt/gino/backups/` |
| Settings, API key and Telegram token | `/etc/gino/gino.env` (only root and Gino can read it) |
| The code (a copy of GitHub `main`) | `/opt/gino/app/` |

**Restoring a backup:** `gino stop`, then
`tar -xzf /opt/gino/backups/<the one you want>.tar.gz -C /opt/gino/data && rm -f /opt/gino/data/gino.db-wal /opt/gino/data/gino.db-shm && chown -R gino:gino /opt/gino/data`,
then `gino start`.

## Good to know

- **Updates only follow `main`.** Code in a pull request reaches Gino once it's merged.
- **Running the install command again is safe.** It repairs things and keeps his memories and settings.
- **Security:** only the website (with the password) and ssh are open to the internet. The API key never leaves the
  server and isn't in GitHub. Choose a long root password, and don't share the page password.
- **Your own web address:** if you buy a domain, point it at the server's IP and rerun the installer with
  `curl -fsSL .../install.sh | GINO_DOMAIN=gino.example.com bash`.
- **Private repo:** the one command assumes the GitHub repo is public. If you make it private again, create a
  read-only fine-grained token for it on GitHub (Contents: read) and install with
  `curl -fsSL -H "Authorization: Bearer <token>" .../install.sh | GITHUB_TOKEN=<token> bash`.
- **Stopping for good:** delete the server in the Hetzner console. Billing stops right away (it's charged by the hour).
  Run `gino backup` and copy `/opt/gino/backups` to your computer first if you want to keep his memories.
