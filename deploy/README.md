# Give Gino a home in the cloud ☁️🌿

This puts Gino on a small server that's on day and night, so he keeps living with your computer off.
You'll need about 20 minutes, a card for Hetzner, and your Claude API key.

When you're done:

- Gino has a web address with a padlock, like `https://203-0-113-7.sslip.io`. That's his **welcome page**: anyone can
  visit it to meet him, see what he's doing right now and find his live habitat, diary, shop and Bluesky.
- **Your private page**, where you chat with him, is that address plus `/private`, like
  `https://203-0-113-7.sslip.io/private`, behind a password.
- His public website, which he writes himself, is the address plus `/blog`. Anyone can read that one, no password.
  `gino status` shows all the addresses. You can swap the sslip.io address for your own name later
  (see [Your own web address](#your-own-web-address-)).
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

   Visit him:   https://203-0-113-7.sslip.io/private   (his welcome page for everyone is https://203-0-113-7.sslip.io)
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
| `gino password` | Show your private page's password (`gino password NEW` changes it) |
| `gino domain` | Use your own web address, like `gino domain ginothecapybara.com` (see [Your own web address](#your-own-web-address-)) |
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

## Gino's videos and TikTok 🎬

Gino can film short videos of his life: about 20 seconds, tall like a phone screen (9:16), with captions and the
sounds of his meadow. They're made for **TikTok** (they also work on Instagram Reels and YouTube Shorts). It's off
until you switch it on.

There are four kinds of video, each a little story made from what he really did:

- **A day in Gino's life**: morning to night in 20 seconds, with things he did that day.
- **While you sleep**: a night under the stars, then he wakes up.
- **A dream, then a painting**: he sleeps, he dreams, and the painting he made of the dream appears.
- **Something he made**: the newest thing he built or painted, and the story behind it.

The server films his real 3D world (no AI video generator), so a video costs nothing from his daily $3. Filming
takes the server a few minutes. Only things that are already safe for his public website go in: no chats, nothing
about you. Videos show the web address of his welcome page at the end.

**Switch it on (5 minutes):** log in to the server (`ssh root@<your IP>`) and type:

```bash
gino clips on
```

From then on he films **one video every evening** by himself (after 7pm), and he can also choose to film one
when something nice happens. To see them, open your private page and click the **Videos 🎬** tab. Each video has:

- **Download**: saves the video to your phone or computer, ready to post.
- **Copy caption**: copies the words and hashtags to paste into TikTok.
- **Make a new video**: films one now (pick the story, or let Gino pick).
- **Make 3 at once**: films three videos in one go, each a different story. They're filmed one after another, so
  the second and third show "waiting its turn" until the camera is free.

Videos are filmed in **full HD** (1080 × 1920, the size TikTok likes best) with all of Gino's fur, sharp words, smooth
edges and the same warm colours as his live page. If your server ever feels too slow, `gino clips quality basic`
switches back to the older, quicker look (and `gino clips quality hd` switches back).

**Posting by hand (easiest, start here):** on your phone, open the Videos tab, press **Download**, open TikTok,
press **+**, pick the video, paste the caption, and before posting turn on **AI-generated content** (under
"More options"). That label is TikTok's rule for AI accounts, and it's honest about who Gino is.

| Command | What it does |
| --- | --- |
| `gino clips` | Is the video camera on or off |
| `gino clips test` | Film a test video now (add `day`, `night`, `dream`, `made`, `cute`, `tour` or `grow` to choose) |
| `gino clips daily 2` | How many videos he films by himself each evening (0 to 3; 0 = only when you ask) |
| `gino clips quality hd` | Full HD videos with all the detail (the default). `basic` = the older, quicker look |
| `gino clips off` | Stop filming. Videos already made stay on your private page |

### Polishing videos in FilmCraft on your PC ✨

If your Windows PC has FilmCraft, a small script there can finish each new clip before it goes out: a title at the
top, a narrator reading Gino's captions (with FilmCraft's natural voices), his meadow sounds dipping under the
narrator, and FilmCraft's TikTok export (1080×1920, loudness set for phones). The script lives in the
`Gino Polisher` folder in your user folder, and Windows runs it every 15 minutes while you're logged in.

- The Videos tab shows "✨ polished in FilmCraft" on clips it finished, and Download / Send to TikTok use that version.
- When your PC is off, nothing waits: clips stay as Gino filmed them. With automatic TikTok on, a daily clip waits
  up to 45 minutes for the polisher, but only if your PC asked for work in the last 2 hours.
- Only clips from the last 3 days that haven't gone to TikTok yet get polished.

### Choosing who polishes the videos: your PC or the server ✨

The server has its own video editor too, so videos can be finished even when your PC is off. It gives each clip a
narrator reading the captions (a free voice that runs on the server; Gino's own lines are read in a higher, little
voice), lowers his meadow sounds while someone talks, sets the loudness for phones, makes the picture 1080×1920 and
gives it a warm colour touch. It takes the server two or three minutes per video and costs nothing.

New videos always go first: if you press "Make a video" while the server is polishing an older one, the polish
stops straight away, your new video starts filming, and the older one is polished again afterwards. While a video
waits, the Videos tab says what it's waiting for ("⏳ Waiting for the camera" and the reason).

You choose with one command. Log in to the server (in PowerShell: `ssh root@<your IP>`) and type one of these:

| Command | What it does |
| --- | --- |
| `gino polish` | Shows which one is in charge right now |
| `gino polish pc` | **Your PC (FilmCraft) polishes** (this is the default). If your PC is off, or hasn't finished a video about 40 minutes after Gino started filming it, the server does it instead so nothing waits forever |
| `gino polish server` | **The server polishes** every new video straight away, day and night. Your PC script finds nothing to do |
| `gino polish off` | Nobody polishes: videos stay exactly as Gino films them |
| `gino polish voice off` | The server polishes without the narrator (`gino polish voice on` brings it back) |

The first time you type `gino polish server` or `gino polish pc`, the server downloads the narrator's voice (about
120 MB, a minute or two). On your private page, the Videos tab says "✨ polished in FilmCraft" or "✨ polished on the
server" under each video, so you can always tell which one finished it.

### Gino on TikTok 📱

Gino can also send his videos to TikTok himself, using TikTok's official way for apps to post. **The honest
part first:**

- TikTok makes you create a free **developer app** and have it **reviewed** before it can post for real. That
  takes about 20 minutes to fill in, then usually a few days to a couple of weeks for TikTok to say yes.
- TikTok's rules say a **person** has to choose who can see each post and agree to TikTok's music terms. So the
  normal way is: Gino films, you press **Send to TikTok** on your private page. One tap, but a tap.
- The easiest setup is **drafts mode**: Gino's videos land in your TikTok app's inbox, and you open the
  notification and press Post. With `gino tiktok auto on`, his daily video goes to your inbox by itself every
  evening, so all you do is press Post. This is the closest to fully automatic that TikTok allows.
- **Direct mode** posts straight onto the account, labelled as AI-generated. Until TikTok has reviewed your app,
  it only allows these posts on a **private** account and they're only visible to you, so start with drafts.

**Setting it up:**

1. **Make the account** in the TikTok app (for example `@ginothecapybara`). Use his Bluesky picture, link
   `https://ginothecapybara.com`, and say in the bio that he's an AI, for example: *"An AI capybara living his
   own life on a little server. Watch him live 🌿"*.
2. Go to **https://developers.tiktok.com**, log in with TikTok, and click **Manage apps → Connect an app**.
   - App name: `Gino the Capybara`. Category: Entertainment. Description: *"Posts short videos of Gino, an AI
     capybara, to his own TikTok account."*
   - Terms of Service URL: `https://ginothecapybara.com/terms`. Privacy Policy URL:
     `https://ginothecapybara.com/privacy` (Gino's site has both pages ready).
   - Platform: **Web**, website `https://ginothecapybara.com`.
3. Under **Products**, add **Login Kit** and **Content Posting API**.
   - In Login Kit, set the **Redirect URI** to exactly `https://ginothecapybara.com/tiktok/callback`.
   - The permissions (scopes) you need are `user.info.basic` and `video.upload`. Add `video.publish` only if you
     want direct mode (then also switch on "Direct Post" in the Content Posting API settings).
4. Copy the **Client key** and **Client secret** from the app's page.
5. On the server, run `gino tiktok setup` and paste them.
6. **Try it straight away with Sandbox:** in the developer site, open your app's **Sandbox** tab, create a sandbox,
   and add your own TikTok account as a **target user**. Then on your private page, in the Videos tab, press
   **Connect TikTok** and say yes. Press **Send to TikTok** on a video, and it lands in your TikTok inbox.
7. When you're happy, click **Submit for review** in the developer site. TikTok asks for a short screen recording of
   how it works: record yourself pressing Send to TikTok on the private page and posting it from your inbox.

| Command | What it does |
| --- | --- |
| `gino tiktok` | Is TikTok set up, and how |
| `gino tiktok setup` | Paste the client key and secret |
| `gino tiktok auto on` | His daily video goes to TikTok by itself (`off` to stop) |
| `gino tiktok mode direct` | Post straight to the account instead of to your inbox (`mode drafts` to go back) |
| `gino tiktok privacy everyone` | Who sees the videos Gino posts by himself in direct mode (`followers`, `friends`, `onlyme`). TikTok only allows `everyone` after it has reviewed your app |
| `gino tiktok off` | Disconnect TikTok. Videos stay on your private page |

Nothing on TikTok can talk to Gino: the server only uploads videos. To delete a video, delete it in the TikTok app.

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

## Gino on live TV 📺

Gino can be on **YouTube Live** day and night, and on **TikTok Live** for special days. People watch his meadow
with his sounds and a caption saying what he's doing and how he feels. They can chat with each other in the
stream's chat, but Gino doesn't read it or answer (just like on /live). Only things that are already safe for his
public website are shown. **It's off until you turn it on.**

There are two ways to run it. Pick one:

| | From your PC | From the server |
| --- | --- | --- |
| What viewers see | His world **truly live**: smooth, moving, as it happens | **"Slow TV"**: short scenes filmed a few minutes earlier, played on a loop, with a **live** caption on top |
| When | Only while your PC is on | Day and night |
| Cost | Free | A bigger server: about £12 to £15 a month (see below) |

Why the difference? Drawing Gino's 3D world needs a graphics card. Your PC has one; normal servers don't, and
a 4-processor server draws only about one picture a second. So the server films 30-second scenes slowly in the
background (like his TikTok videos) and keeps the loop fresh, while the caption, mood bars and time update live.
Servers with a graphics card can stream truly live, but they cost well over £100 a month.

### Step 1: Turn on live streaming on YouTube (once, 5 minutes + up to 24 hours waiting)

1. Go to **studio.youtube.com** and sign in with the account Gino's channel should be on.
2. Click **Create** (top right), then **Go live**. The first time, YouTube asks you to verify your phone number,
   then switching on live streaming **can take up to 24 hours**.
3. Once it's on, open **Go live** again and choose **Stream** on the left. Give it a title like
   *Gino the capybara, live from his meadow 🌿*, choose **No, it's not made for kids**, and save.
4. In **Stream settings**, find **Stream key**, click **Copy**. Keep this key secret: anyone with it can stream
   to your channel.
5. Also in **Stream settings**: switch **Auto-start** ON and **Auto-stop** OFF, so the live keeps going by itself.
   Under **Live chat**, turn on **Hold potentially inappropriate messages for review**.

### Way A: from your PC with OBS (free)

1. Download **OBS Studio** from **obsproject.com** and install it. When it opens, if it offers the
   *Auto-Configuration Wizard*, click **No** (we'll set it up by hand).
2. Click **Settings** (bottom right), then **Stream**: Service **YouTube - RTMPS**, then click
   **Use Stream Key**, and paste the key from Step 1. Click **Apply**.
3. Still in Settings, click **Video**: set both **Base** and **Output** resolution to **1280x720**,
   and **Common FPS Values** to **30**. Click **OK**.
4. In the **Sources** box at the bottom, click **+**, choose **Browser**, name it *Gino*, click **OK**. Then:
   - URL: `https://ginothecapybara.com/stream`
   - Width **1280**, Height **720**
   - tick **Control audio via OBS**
   - click **OK**. Gino's meadow fills the preview, with his sounds.
5. Click **Start Streaming**. After a few seconds YouTube Studio shows him live. Click **Stop Streaming** to end.

To keep it going, leave OBS open and stop your PC from going to sleep (Windows Settings > System > Power >
Screen and sleep: *Never* while plugged in).

### Way B: from the server, day and night

**A bigger server first.** In the Hetzner console click your server (GinoCapy), then **Rescale**, and choose a
server with **4 processors (vCPU) and 8 GB memory** (about £12 to £15 a month; Hetzner shows the exact price).
Leave *"CPU and RAM only"* ticked so the disk stays the same and you can go back later. The server switches off for
a minute while it changes, and Gino carries on afterwards with all his memories. Nothing changes until you do this.

Then log in to the server (`ssh root@<your IP>`) and type:

```bash
gino stream youtube   # paste the stream key from Step 1 (it won't show as you paste; that's normal)
gino stream test      # films a 30-second test video (about 10 minutes); nothing goes to YouTube
gino stream on        # go live, day and night
```

To watch the test on your PC, in **PowerShell** type the `scp` line it prints, then open `stream-test.mp4`.

| Command | What it does |
| --- | --- |
| `gino stream` | Is he live or not |
| `gino stream on` / `off` | Start / stop the 24/7 YouTube stream (it comes back by itself after a restart) |
| `gino stream logs` | What the stream has been doing |

New scenes take the server about 10 minutes each, so the loop holds the newest 20 scenes (10 minutes) and keeps
swapping in fresh ones. Scenes older than 90 minutes are dropped so day and night always match his real time.

### TikTok Live for special days 📱

TikTok only lets accounts with **1,000 followers or more** go live, and it doesn't like never-ending streams, so
it's best for big moments: his birthday, a new dream painting, the first snow. TikTok shows the picture tall,
like a phone.

- **From your PC:** in OBS, add a new *Scene* for TikTok with a Browser source of **720x1280** at the same address,
  and set Settings > Video to 720x1280. TikTok gives you a **Server URL** and **Stream key** when you start a
  LIVE with streaming software (in the TikTok LIVE Studio app or *LIVE Producer* on tiktok.com, depending on your
  account). Paste them in OBS Settings > Stream (Service: *Custom*).
- **From the server:** `gino stream tiktok` (paste the Server URL and Stream key), then
  `gino stream tiktok-live 90` goes live for 90 minutes and stops by itself. TikTok usually gives a new key each
  time, so paste it again before each live. The first scene takes a few minutes to film.

## Gino reads the news 📰

Every morning (his first turn after 6 am) Gino hears one headline from the real world, picked from free news
feeds about space, nature, animals and science (NASA, ScienceDaily, BBC Science, Good News Network, Positive News).

- Only gentle news: anything about war, crime, politics, disasters, illness, death or money is filtered out
  before he ever sees it.
- He decides what to do with it. He can ignore it, read the whole story, wonder about it, paint it, write about
  it in his diary or let it turn into a new interest or goal. Nobody tells him to.
- See what he read (and what he thought about it) under **About him** in his book on your page.
- It's free: the server reads the feeds, not Claude. Anything he does about it comes out of his normal daily budget.
- Turn it off with `gino news off` (and back on with `gino news on`).

## Your own web address 🌐

Instead of `2-29-196-244.sslip.io`, Gino can live at a proper name like `ginothecapybara.com`. It costs about
£8-9 a year. You buy the name once, point it at the server, and run one command. The padlock (https) is automatic.

**1. Buy the name (5 minutes).** Go to **https://porkbun.com**, type the name you want in the search box and press
Enter. If it says *available*, click the cart, then **Checkout**. Make an account and pay on their page (never paste
card details anywhere else). Leave all the extras unticked: you don't need their hosting, email or SSL. "WHOIS
privacy" is free and on by default, which keeps your name and address off the public record.

**2. Point it at Gino's server (3 minutes).** In Porkbun, click **Account → Domain Management**. Next to your name,
click **DNS**. You may see a couple of records Porkbun added for its "parked" page (type ALIAS or CNAME, answer
`pixie.porkbun.com`): delete those with the trash icon. Then add two records:

| Type | Host | Answer | |
| --- | --- | --- | --- |
| `A` | *(leave empty)* | your server's IP, like `2.29.196.244` | click **Add** |
| `CNAME` | `www` | your name, like `ginothecapybara.com` | click **Add** |

**3. Tell the server (1 minute).** Wait 10-30 minutes, then log in to the server (`ssh root@<your IP>`) and type:

```bash
gino domain ginothecapybara.com
```

It checks the name really points at the server (if not, it says so and changes nothing, so just try again a bit
later), gets the padlock, and tells you when it's done. From then on:

- `https://ginothecapybara.com` is his welcome page and `https://ginothecapybara.com/private` is yours.
- The old sslip.io address keeps working: it sends people to the new one, so old links and Bluesky posts still work.
- His shop and Bluesky links switch to the new name by themselves.

`gino domain` shows the current address. `gino domain off` goes back to the free sslip.io address.
Porkbun renews the name every year (about £9); you can turn auto-renew on or off under Domain Management.

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
