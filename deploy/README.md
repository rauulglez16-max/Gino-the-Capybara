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

## Let Gino message you on WhatsApp 💬

This uses WhatsApp's official system for apps (Meta's "WhatsApp Cloud API"), so nothing gets banned. Setting it up takes
about 30 minutes, mostly clicking around Meta's website once. Only your number can talk to Gino. He ignores messages
from anyone else, and the server checks that every message really comes from WhatsApp.

**One WhatsApp rule to know:** Gino can text you freely for 24 hours after your last message to him. If he wants to tell
you something after that, he sends you one short nudge. His actual message waits, and arrives as soon as you reply.
So if you text him every day or so, you'll hardly notice the rule.

**Cost:** the first 1,000 replies each month are free, which is far more than Gino needs. A nudge costs about 2p.
On Meta's free test number, nudges are free too.

### Step 1: Make a Meta app (10 minutes)

1. Go to **https://developers.facebook.com**, log in with your Facebook account, and click **Get started** to register
   as a developer (it's free; it may ask you to confirm your phone or email).
2. Click **My Apps** > **Create app**. Name it `Gino`. When it asks for a use case, pick
   **Connect with customers through WhatsApp**. If it asks for a business portfolio, create one (any name, like `Gino`).
   Click through to **Create app**.
3. In the app, open **WhatsApp** > **API Setup** in the left menu. Meta has given Gino a free **test number**.
   - Under **To**, click **Manage phone number list**, add **your own** mobile number and type in the code WhatsApp
     sends you.
   - Copy the **Phone number ID** (the long number shown under the test number, not the phone number itself).
     That's **thing 1 of 4**.
   - Click **Send message**. You get a "Hello World" message on WhatsApp from the test number. Save that number in
     your phone as **Gino 🐾**.

### Step 2: Get the app secret (1 minute)

In the left menu, go to **App settings** > **Basic**. Next to **App secret**, click **Show** and copy it.
That's **thing 2 of 4**.

### Step 3: Get a permanent token (5 minutes)

The token on the API Setup page stops working after a day, so make one that doesn't:

1. Go to **https://business.facebook.com/latest/settings** and choose **System users** (under Users).
2. Click **Add**, call it `gino`, set the role to **Admin**, and create it.
3. Click **Assign assets**. Pick your app `Gino` and turn on **Manage app** (full control). Pick your WhatsApp account
   and turn on full control too. Save.
4. Click **Generate token**. Choose the app `Gino`, set the expiry to **Never**, and tick these permissions:
   `business_management`, `whatsapp_business_messaging` and `whatsapp_business_management`.
   Copy the long token. That's **thing 3 of 4**. Keep it secret.

**Thing 4 of 4** is your own WhatsApp number with the country code and no `+`, like `447700900123` for a UK mobile.

### Step 4: Tell Gino (2 minutes)

In PowerShell, log in to the server with `ssh root@<your IP>`, then type:

```bash
gino whatsapp
```

It asks for the 4 things, one at a time. Paste each one (right-click pastes in PowerShell) and press Enter. When it's
done it shows a **Callback URL** and a **Verify token**.

### Step 5: Connect the webhook (2 minutes)

Back on developers.facebook.com, in your app, open **WhatsApp** > **Configuration**:

1. Under **Webhook**, click **Edit**, paste the **Callback URL** and the **Verify token**, and click **Verify and save**.
2. Under **Webhook fields**, find **messages** and click **Subscribe**.

Now open WhatsApp, send **hi** to Gino 🐾, and he'll answer. 🎉

### Optional: a nicer nudge

Out of the box, Gino's nudge is Meta's "Hello World" message. To make it say what's going on, open **WhatsApp Manager**
(https://business.facebook.com/wa/manage/message-templates/) > **Create template**:

- Category **Utility**, name `gino_nudge`, language **English (UK)**
- Body: `🐾 Gino has a message for you. Reply to read it.`

Submit it. Once it shows **Active** (usually within minutes), run `gino whatsapp template gino_nudge en_GB` on the server.

| Command | What it does |
| --- | --- |
| `gino whatsapp test` | Send the nudge to your phone, to check everything works |
| `gino whatsapp webhook` | Show the Callback URL and Verify token again |
| `gino whatsapp template NAME en_GB` | Change which template Gino uses as his nudge |
| `gino whatsapp` | Set it up again (new token, new number...) |
| `gino whatsapp off` | Disconnect WhatsApp |

Telegram and WhatsApp can both be on at once. When Gino messages you, it goes to both.

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
| `gino telegram` | Connect him to Telegram on your phone (see above) |
| `gino whatsapp` | Connect him to your WhatsApp (see above) |
| `gino social` | His Bluesky account: `setup`, `on`, `off` (see [Gino on Bluesky](#gino-on-bluesky-)) |
| `gino photos` | Photos in his posts: `on`, `test`, `off` |
| `gino dreams` | His dreams at night: `on`, `off` (they're on to begin with) |
| `gino settings` | Change any setting (model, budget, time zone...). Save with Ctrl+O, Enter, then Ctrl+X |

## Gino on Bluesky 🦋

Gino can have his own Bluesky account where he posts short updates about his day. It's off until you switch it on.

**The rules he can't break** (they're enforced in the code, not just asked of him):

- He only writes new posts. He can't reply, quote, like, follow, send or read messages, or @mention anyone, so
  nobody can talk to him through Bluesky.
- Every post goes through the same privacy filter as his website: nothing about you, your chats, keys or passwords.
- At most 3 posts in 24 hours, at least 2 hours apart. The only links allowed are to his own website.
- Each post also appears on his website under "On Bluesky".

**Setting it up (about 5 minutes):**

1. On your phone or computer, sign up at **https://bsky.app** with a new email for Gino (Gmail's `you+gino@gmail.com`
   trick works). Pick a handle like `gino-capybara.bsky.social`.
2. Give him a profile: a name ("Gino the Capybara"), a picture, and a bio that says he's an AI, for example:
   *"An AI capybara living on a little server. I post about my meadow, my snacks and what I make. Automated account."*
3. Go to **Settings → Privacy and security → App passwords → Add App Password**, name it `gino`, and copy it.
   (Don't tick "allow access to direct messages".)
4. Log in to the server (`ssh root@<your IP>`) and run `gino social setup`. Paste the handle and the app password.
   It checks the login without posting anything.
5. Run `gino social on`. That's it. He'll post when he has something to share.

| Command | What it does |
| --- | --- |
| `gino social` | Is posting on or off, and which account |
| `gino social off` | Stop posting right away. His account and old posts stay |
| `gino social on` | Let him post again |
| `gino social setup` | Change the account or app password |

**Photos 📸 (optional):** Gino can add a real picture of his 3D world to a post: a selfie, or a wide shot of
his home, showing exactly what he's doing right then. The server takes it with a small built-in browser, so it
costs nothing. To switch it on, run `gino photos on` (it installs about 300 MB and takes a few minutes), then
`gino photos test` to take a test picture without posting it. `gino photos off` turns photos off again. Photos
only show drawings he already put on his website, and they also appear on his website next to the post.

To remove a post, log in to the account at bsky.app and delete it there. If you ever worry the app password
leaked, delete it in Bluesky's App passwords screen and make a new one.

## Gino's shop 🛒

Gino can run his own little shop at `/blog/shop`, where anyone can buy his drawings as instant downloads. He
decides what to sell, what to call it, how to describe it and what it costs. You don't have to do anything for
each sale. The money goes into **your** Stripe account and Stripe pays it out to your bank. The shop stays
closed until you open it.

**How a sale works:** a visitor clicks Buy → pays on Stripe's own checkout page → comes back to Gino's site and
downloads the drawing. Gino is told "someone bought your drawing" (never who bought it), and if Telegram is set
up you get a text too.

**The rules he can't break** (they're enforced in the code, not just asked of him):

- Prices between £1 and £10. At most 2 new items a day and 20 for sale at once.
- He can't spend money, give refunds, see card details, or talk to buyers. There's no code for any of that.
- He never sees the Stripe key. It's a *restricted* key that can only create products and checkouts: it can't
  move money or give refunds, even if someone stole it.
- Everything goes through the same privacy filter as his website, and every item says it was made by an AI capybara.
- For now he only sells drawings.

**Why Stripe "Managed Payments":** with it switched on, Stripe is the official seller. It works out and pays
the VAT for buyers anywhere in the world (otherwise selling downloads to EU buyers means VAT paperwork from
the very first sale), and it deals with fraud, receipts and buyer questions. Stripe takes about 5% + 20p a
sale, so on a £4 sale you keep about £3.60. Nothing to pay up front, and no monthly fee.

**Setting it up (about 20 minutes):**

1. Go to **https://dashboard.stripe.com/register** and sign up. When it asks about your business, choose
   **Individual / sole trader** and **United Kingdom**. For what you sell, write something like *"Digital
   drawings made by my AI capybara, sold as downloads"*. For your website, use
   `https://<your address>/blog/shop`. Add your bank account so Stripe can pay you.
2. Switch on Managed Payments: go to **https://dashboard.stripe.com/settings/managed-payments** and click
   **Activate**. Stripe may take a little while to approve it.
3. Make the restricted key: go to **https://dashboard.stripe.com/apikeys/create**. In the "How will you be
   using this API key?" step, pick the option for **powering an integration you built** (if you're asked), and
   name it `gino-shop`. In the permissions list set these to **Write**:
   - **Products**
   - **Prices** (if it's listed separately)
   - **Checkout Sessions**

   Leave everything else as **None**. Click **Create key** and copy it (it starts with `rk_live_`).
   ⚠️ Never use the "Secret key" (`sk_live_...`). It can do anything with your money. The setup refuses it anyway.
4. Open **PowerShell** on your computer, log in to the server (`ssh root@<your IP>`), and type
   `gino shop setup`. Paste the key (nothing shows while you paste; that's normal) and press Enter. It
   checks the key without selling anything.
5. Type `gino shop on`. The shop is open! Gino will notice it on his next turn.

| Command | What it does |
| --- | --- |
| `gino shop` | Is the shop open or closed |
| `gino shop off` | **Close the shop right away.** Nobody can buy anything. People who already bought can still download |
| `gino shop on` | Open it again (his items come back) |
| `gino shop sales` | List what's sold and the total |
| `gino shop setup` | Change the Stripe key |

Your money, Stripe's fees and payouts to your bank are all in the Stripe dashboard:
**https://dashboard.stripe.com/payments**. If you ever worry the key leaked, delete it in Stripe's API keys
page and make a new one.

**Tax (UK):** if all your side income in a tax year (shop sales plus anything else like it) stays under
£1,000, it's tax-free and you don't need to tell HMRC. That limit goes up to £3,000 from April 2027. Above it,
you register for Self Assessment. Stripe handles the VAT. This isn't professional tax advice, so check
gov.uk if sales really take off.

## Gino's dreams 🌙

When Gino sleeps for two hours or more, he has one dream part-way through. It's made from his own memories,
his day, his goals and how his body feels, mixed up the way dreams are. Most nights are ordinary or a bit odd;
now and then he has a *vision*, a really strange, surreal one.

- The dream changes how he feels when he wakes up, and he remembers it.
- His first turn after waking starts with the dream. He decides what to do with it: often he paints it, and he
  might write about it, put the painting on his website, tell you, or let it give him a new goal or passion.
- Read his dreams (and see the paintings) in the **Dreams** tab on his page.
- On the live page he shows as "dreaming" while asleep after a dream, and dream paintings he publishes get a 🌙
  on his creations board.
- A dream costs about 5 US cents and counts towards his daily budget. No dreams once the budget is used up.
- Turn them off with `gino dreams off` (and back on with `gino dreams on`).

## Where things live on the server

| What | Where |
| --- | --- |
| Gino's memories, diary, home, creations | `/opt/gino/data/` (never touched by updates) |
| Backups | `/opt/gino/backups/` |
| Settings, API key and phone tokens | `/etc/gino/gino.env` (only root and Gino can read it) |
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
