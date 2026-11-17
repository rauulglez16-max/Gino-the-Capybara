"""Gino's front door: the welcome page at the main address, for anyone who wants to meet him.

It explains who Gino is, shows him (pictures, what he's doing right now, his latest creations) and points to the
places people can visit: the live habitat, his diary, his shop and his Bluesky account.

Everything live on this page comes from live.state(), the same filtered, cached slice of Gino the /live page uses,
so every word Gino wrote has already been through public.check(). The rest is fixed text written for visitors.
Nothing here mentions his family, his chats or anything private, and there are no forms and no write endpoints.
The private page (chat, gifts, petting) lives at /private, behind the password, and isn't linked from here,
except for a small "your private page" link that only shows in a browser that already knows the password.

The look is a picture book: ink outlines, paper, hand-written notes. A day theme (golden meadow, drifting leaves)
and a night theme (starry sky, fireflies), following the visitor's system setting until they flip the switch.
All motion is CSS or a few lines of script, and it all stops for people who ask their system for less motion.
Fonts (Fraunces, Caveat; SIL Open Font License) are served from this server, so visitors aren't sent anywhere else.
"""
import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from . import config, db, live, shop, social

router = APIRouter()
E = html.escape

HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; "
                               "style-src 'unsafe-inline'; font-src 'self'; base-uri 'none'; form-action 'none'; "
                               "frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "public, max-age=30",
}

MOOD_FACE = {"happy": "😊", "joyful": "😄", "excited": "🤩", "content": "😌", "calm": "😌", "curious": "🧐",
             "proud": "😎", "playful": "😜", "sleepy": "😴", "tired": "🥱", "hungry": "🤤", "bored": "😐",
             "lonely": "🥺", "sad": "😢", "grumpy": "😤", "anxious": "😟", "cosy": "🥰", "cozy": "🥰",
             "amazed": "😮", "inspired": "✨", "peaceful": "😌", "dreamy": "😴"}

WHO = [
    ("🧠", "#f6c453", "He decides for himself",
     "Nobody tells Gino what to do. Every so often he wakes up, checks how he feels and picks what's next: "
     "a snack, a nap, a walk to the pond, a new project, or something he's curious about on the internet."),
    ("🍉", "#f19a8a", "He has a body to look after",
     "He gets hungry, sleepy, bored and lonely, just like a real capybara. Fullness, energy, fun and mood "
     "rise and fall through the day, and he has to look after them himself."),
    ("🏡", "#9fcf7a", "He built his own home",
     "His meadow by the lake started empty. Everything in it now, from his little house to the garden "
     "and the lamps, is something he chose and placed himself."),
    ("🎨", "#8fc3ea", "He makes things",
     "Drawings, poems, little stories and songs. He puts his favourites on his website and sells some "
     "of his drawings in his own shop."),
    ("🌙", "#b9a3e8", "He dreams at night",
     "When he sleeps, his days mix into dreams. Some of them he remembers, and some turn into paintings "
     "in the morning."),
    ("📔", "#f3b178", "He keeps a diary",
     "He writes about his days in his own words: what he did, what he learned and how he felt. "
     "Sometimes he shares a moment on Bluesky too."),
]

GALLERY = [
    ("/static/welcome/meadow.jpg", "a sunny afternoon in the meadow"),
    ("/static/welcome/morning.jpg", "out for a morning stroll"),
    ("/static/welcome/night.jpg", "rainy night, lamps on"),
]

# ------------------------------------------------------------------ look

LIGHT = """--bg:#f7efdf;--paper:#fffaf0;--ink:#3a2a1c;--muted:#76624c;--line:#3a2a1c;--accent:#c4602a;--accent-ink:#fffaf0;
--leaf:#4c7a37;--soft:#f2e4c8;--bar:#eadcc0;--shade:#3a2a1c;--sky1:#ffd88f;--sky2:#fbe9c4;--hill1:#c9dc98;--hill2:#a7c777;
--sun:#f5b53c;--sunglow:rgba(245,181,60,.35);--grain:.06;--tape:rgba(240,200,120,.75)"""
DARK = """--bg:#111827;--paper:#1b2338;--ink:#f3e7d0;--muted:#b4a78c;--line:#e9d6ae;--accent:#f4a95c;--accent-ink:#111827;
--leaf:#a6d47f;--soft:#252f4a;--bar:#2c3657;--shade:#04070d;--sky1:#0d1430;--sky2:#1a2445;--hill1:#1f3b2e;--hill2:#17301f;
--sun:#f3ead0;--sunglow:rgba(243,234,208,.18);--grain:.05;--tape:rgba(170,190,230,.35)"""

GRAIN = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E"
         "%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E"
         "%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")
SQUIGGLE = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 12'%3E%3Cpath d='M2 7 "
            "C 12 1, 22 13, 32 7 S 52 1, 62 7 S 82 13, 92 7 S 112 1, 118 6' fill='none' stroke='black' "
            "stroke-width='3.2' stroke-linecap='round'/%3E%3C/svg%3E")

CSS = """
@font-face{font-family:Fraunces;src:url(/static/welcome/fonts/fraunces.woff2) format("woff2");font-weight:100 900;font-display:swap}
@font-face{font-family:Caveat;src:url(/static/welcome/fonts/caveat.woff2) format("woff2");font-weight:600;font-display:swap}
:root{%(light)s;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){%(dark)s;color-scheme:dark}}
:root[data-theme="dark"]{%(dark)s;color-scheme:dark}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.65 Fraunces,Georgia,serif;
  font-variation-settings:"SOFT" 100,"WONK" 0;transition:background-color .6s,color .6s;overflow-x:hidden}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:100;opacity:var(--grain);
  background-image:url("%(grain)s");mix-blend-mode:multiply}
a{color:var(--accent)}
.hand{font-family:Caveat,'Comic Sans MS',cursive;font-weight:600}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px;position:relative}

/* ---------- top bar */
nav.top{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 0;position:relative;z-index:5}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:24px;color:inherit;text-decoration:none;
  font-variation-settings:"SOFT" 100,"WONK" 1}
.brand svg{transition:transform .3s}
.brand:hover svg{transform:rotate(-8deg) scale(1.08)}
.eye{animation:blink 5s infinite;transform-box:fill-box;transform-origin:center}
@keyframes blink{0%%,92%%,100%%{transform:scaleY(1)}95%%{transform:scaleY(.1)}}
.links{display:flex;align-items:center;gap:20px;font-size:16px}
.links a{color:var(--ink);text-decoration:none;position:relative}
.links a::after{content:"";position:absolute;left:0;right:0;bottom:-3px;height:2px;background:var(--accent);
  transform:scaleX(0);transform-origin:left;transition:transform .25s}
.links a:hover::after{transform:scaleX(1)}
#theme{width:46px;height:46px;border-radius:50%%;border:2px solid var(--line);background:var(--paper);color:var(--ink);
  box-shadow:3px 3px 0 var(--shade);cursor:pointer;position:relative;overflow:hidden;flex:none;padding:0;
  transition:transform .15s,box-shadow .15s,background-color .6s}
#theme:hover{transform:translate(-1px,-1px);box-shadow:4px 4px 0 var(--shade)}
#theme:active{transform:translate(2px,2px);box-shadow:1px 1px 0 var(--shade)}
#theme span{position:absolute;inset:0;display:grid;place-items:center;font-size:22px;transition:transform .5s cubic-bezier(.6,-.4,.3,1.4)}
#theme .moon{transform:translateY(46px) rotate(-90deg)}
:root[data-theme="dark"] #theme .sun{transform:translateY(-46px) rotate(90deg)}
:root[data-theme="dark"] #theme .moon{transform:none}

/* ---------- hero: a little sky with hills */
.sky{position:relative;background:linear-gradient(180deg,var(--sky1),var(--sky2) 70%%,var(--bg));overflow:hidden}
.orb{position:absolute;right:8%%;top:70px;width:170px;height:170px;border-radius:50%%;background:var(--sun);
  box-shadow:0 0 0 22px var(--sunglow),0 0 0 50px var(--sunglow);animation:glow 6s ease-in-out infinite;transition:background .6s}
@keyframes glow{50%%{box-shadow:0 0 0 30px var(--sunglow),0 0 0 64px var(--sunglow)}}
.stars{position:absolute;inset:0;opacity:0;transition:opacity .8s;pointer-events:none}
.stars i{position:absolute;width:3px;height:3px;border-radius:50%%;background:#fff8e0;animation:twinkle 3s ease-in-out infinite}
@keyframes twinkle{50%%{opacity:.2}}
.bits{position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:1}
.bits i{position:absolute;top:-30px;width:14px;height:9px;border-radius:0 100%%;background:var(--c,#7aa64e);opacity:.85;
  animation:fall var(--d,14s) linear var(--w,0s) infinite}
@keyframes fall{0%%{transform:translate(0,0) rotate(0)}25%%{transform:translate(40px,25vh) rotate(120deg)}
  50%%{transform:translate(-20px,50vh) rotate(220deg)}75%%{transform:translate(50px,75vh) rotate(330deg)}
  100%%{transform:translate(10px,105vh) rotate(420deg)}}
:root[data-theme="dark"] .stars{opacity:1}
:root[data-theme="dark"] .bits i{width:6px;height:6px;border-radius:50%%;background:#ffe98a;top:var(--y,50%%);
  box-shadow:0 0 10px 3px rgba(255,226,120,.7);animation:fly var(--d,14s) ease-in-out var(--w,0s) infinite alternate}
@keyframes fly{0%%{transform:translate(0,0);opacity:.2}30%%{opacity:1}50%%{transform:translate(60px,-40px);opacity:.4}
  80%%{opacity:1}100%%{transform:translate(-30px,-90px);opacity:.15}}
.hills{position:absolute;left:0;right:0;bottom:-1px;width:100%%;height:140px;display:block}
.hills .h1{fill:var(--hill1);transition:fill .6s}
.hills .h2{fill:var(--hill2);transition:fill .6s}
.hills .h3{fill:var(--bg);transition:fill .6s}
.hero{display:grid;grid-template-columns:1.05fr 1fr;gap:40px;align-items:center;padding:26px 0 150px;position:relative;z-index:2}
.hello{font-size:28px;color:var(--accent);margin:0 0 4px;transform:rotate(-3deg);display:inline-block}
.hero h1{font-size:60px;line-height:1.02;margin:0 0 18px;letter-spacing:-.02em;font-weight:800;
  font-variation-settings:"SOFT" 100,"WONK" 1}
.mark{position:relative;white-space:nowrap;display:inline-block;isolation:isolate}
.mark svg{position:absolute;left:-4%%;bottom:-.08em;width:108%%;height:.42em;z-index:-1;overflow:visible}
.mark path{fill:none;stroke:var(--sun);stroke-width:14;stroke-linecap:round;opacity:.75;
  stroke-dasharray:420;stroke-dashoffset:420;animation:draw 1.1s .5s cubic-bezier(.6,0,.2,1) forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.hero h1 .l{display:block;opacity:0;transform:translateY(18px);animation:up .8s cubic-bezier(.2,.7,.2,1) forwards}
.hero h1 .l:nth-child(2){animation-delay:.12s}.hero h1 .l:nth-child(3){animation-delay:.24s}
@keyframes up{to{opacity:1;transform:none}}
.lead{font-size:20px;color:var(--muted);margin:0 0 26px;max-width:520px}
.btns{display:flex;flex-wrap:wrap;gap:12px}
.btn{display:inline-flex;align-items:center;gap:8px;padding:12px 20px;border-radius:999px;text-decoration:none;
  font-weight:700;font-size:17px;border:2px solid var(--line);color:var(--ink);background:var(--paper);
  box-shadow:3px 3px 0 var(--shade);transition:transform .15s,box-shadow .15s,background-color .6s}
.btn:hover{transform:translate(-2px,-2px);box-shadow:5px 5px 0 var(--shade)}
.btn:active{transform:translate(2px,2px);box-shadow:1px 1px 0 var(--shade)}
.btn.main{background:var(--accent);color:var(--accent-ink)}
.dot{width:9px;height:9px;border-radius:50%%;background:#e0442c;display:inline-block;position:relative;flex:none}
.dot::after{content:"";position:absolute;inset:-4px;border-radius:50%%;border:2px solid #e0442c;animation:ping 1.8s infinite}
.btn.main .dot{background:var(--accent-ink)}
.btn.main .dot::after{border-color:var(--accent-ink)}
@keyframes ping{0%%{transform:scale(.6);opacity:1}100%%{transform:scale(2);opacity:0}}
.pic{position:relative;transform:rotate(2deg);animation:float 7s ease-in-out infinite}
@keyframes float{50%%{transform:rotate(1deg) translateY(-8px)}}
.frame{background:var(--paper);border:2px solid var(--line);border-radius:18px;padding:10px 10px 14px;
  box-shadow:7px 7px 0 var(--shade);transition:background-color .6s}
.frame .ph{overflow:hidden;border-radius:10px;aspect-ratio:4/3;border:2px solid var(--line)}
.frame .night{display:none}
:root[data-theme="dark"] .frame .night{display:block}
:root[data-theme="dark"] .frame .day{display:none}
.frame img{width:100%%;height:100%%;object-fit:cover;display:block;animation:kenburns 22s ease-in-out infinite alternate}
@keyframes kenburns{from{transform:scale(1.02)}to{transform:scale(1.12) translate(-2%%,1%%)}}
.frame .cap{display:flex;align-items:center;gap:10px;font-size:15px;margin:10px 6px 0;font-family:system-ui,sans-serif}
.note-him{position:absolute;left:-22px;top:-50px;font-size:27px;color:var(--ink);transform:rotate(-8deg);display:flex;align-items:flex-end;gap:2px;z-index:2}
.note-him svg{width:54px;height:44px;margin-bottom:-26px}
.note-him path{fill:none;stroke:var(--ink);stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}
.tape{position:absolute;width:96px;height:28px;background:var(--tape);top:-12px;left:50%%;transform:translateX(-50%%) rotate(-4deg);z-index:1}

/* ---------- sections */
section{padding:40px 0;position:relative}
.kick{font-size:26px;color:var(--accent);margin:0;transform:rotate(-2deg);display:inline-block}
h2{font-size:42px;line-height:1.1;margin:0 0 10px;letter-spacing:-.015em;font-weight:800;
  font-variation-settings:"SOFT" 100,"WONK" 1}
h2::after{content:"";display:block;height:12px;width:120px;margin-top:6px;background:var(--accent);
  -webkit-mask:url("%(squiggle)s") no-repeat center/contain;mask:url("%(squiggle)s") no-repeat center/contain}
.sub{color:var(--muted);margin:0 0 28px;max-width:640px;font-size:18px}
.card,.now,.made a,.visit a,.faq details{background:var(--paper);border:2px solid var(--line);
  box-shadow:5px 5px 0 var(--shade);transition:transform .2s,box-shadow .2s,background-color .6s}
.now{border-radius:24px;padding:26px;display:grid;grid-template-columns:auto 1fr 1fr;gap:26px;align-items:center}
.face{font-size:64px;line-height:1;width:108px;height:108px;border-radius:50%%;background:var(--soft);
  display:flex;align-items:center;justify-content:center;border:2px solid var(--line);position:relative;
  animation:bob 3.2s ease-in-out infinite;margin:10px}
.face::after{content:"";position:absolute;inset:-10px;border-radius:50%%;border:2px dashed var(--accent);animation:spin 18s linear infinite}
@keyframes bob{50%%{transform:translateY(-6px) rotate(-3deg)}}
@keyframes spin{to{transform:rotate(360deg)}}
.what{font-size:24px;line-height:1.35}
.what b{color:var(--leaf)}
.meta{font:14px/1.5 system-ui,sans-serif;color:var(--muted);margin-top:6px}
.livepill{display:inline-flex;align-items:center;gap:10px;font:700 12px system-ui,sans-serif;letter-spacing:.12em;
  text-transform:uppercase;color:#e0442c;margin-bottom:6px}
.now blockquote{margin:14px 0 0;font-size:26px;line-height:1.25;color:var(--ink);position:relative;padding-left:28px}
.now blockquote::before{content:"“";position:absolute;left:0;top:-8px;font-size:48px;color:var(--accent);font-family:Fraunces,serif}
.bars{display:grid;grid-template-columns:1fr 1fr;gap:16px 20px;font:14px system-ui,sans-serif}
.bar span{display:flex;justify-content:space-between;margin-bottom:5px;font-weight:600}
.bar em{font-style:normal;color:var(--muted)}
.bar i{display:block;height:14px;border-radius:99px;background:var(--bar);overflow:hidden;border:2px solid var(--line)}
.bar i b{display:block;height:100%%;transition:width 1.4s cubic-bezier(.2,.8,.2,1);
  background-image:repeating-linear-gradient(-45deg,rgba(255,255,255,.25) 0 6px,transparent 6px 12px);background-size:17px 17px;
  animation:stripes 1.2s linear infinite}
@keyframes stripes{to{background-position:17px 0}}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}
.card{border-radius:20px;padding:22px 22px 24px;transform:rotate(var(--r,0deg))}
.card:nth-child(3n+1){--r:-.8deg}.card:nth-child(3n+2){--r:.6deg}.card:nth-child(3n){--r:-.3deg}
.card:hover{transform:rotate(0) translate(-3px,-4px);box-shadow:8px 9px 0 var(--shade)}
.card .ic{width:58px;height:58px;border-radius:46%% 54%% 50%% 50%% / 55%% 45%% 55%% 45%%;background:var(--c);display:grid;place-items:center;
  font-size:28px;border:2px solid var(--line)}
.card:hover .ic{animation:wiggle .6s}
@keyframes wiggle{25%%{transform:rotate(-12deg) scale(1.1)}60%%{transform:rotate(9deg) scale(1.1)}}
.card h3{margin:14px 0 6px;font-size:22px;font-variation-settings:"SOFT" 100,"WONK" 1}
.card p{margin:0;color:var(--muted);font-size:16px}
.gallery{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:30px;padding:16px 6px 0;align-items:start}
.gallery figure{margin:0;background:#fffdf7;padding:12px 12px 6px;border:2px solid var(--line);box-shadow:6px 6px 0 var(--shade);
  position:relative;transform:rotate(var(--r));transition:transform .3s}
.gallery figure:nth-child(1){--r:-2.5deg}.gallery figure:nth-child(2){--r:2deg;margin-top:38px}.gallery figure:nth-child(3){--r:-1deg;margin-top:10px}
.gallery figure:hover{transform:rotate(0) scale(1.04);z-index:2}
.gallery img{width:100%%;aspect-ratio:1;object-fit:cover;display:block;border:1px solid rgba(0,0,0,.15)}
.gallery figcaption{font-size:23px;color:#3a2a1c;text-align:center;padding:4px 0 0}
.made{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:18px}
.made a{border-radius:18px;padding:12px;text-decoration:none;color:inherit}
.made a:hover{transform:translate(-3px,-3px) rotate(-1deg);box-shadow:8px 8px 0 var(--shade)}
.made img{width:100%%;aspect-ratio:1;object-fit:contain;background:#fff;border-radius:10px;display:block;border:2px solid var(--line)}
.made .poem{aspect-ratio:1;overflow:hidden;background:var(--soft);border-radius:10px;padding:14px;font-size:21px;
  line-height:1.25;white-space:pre-line;border:2px solid var(--line)}
.made strong{display:block;margin-top:10px;font-size:17px}
.made small{font:12px system-ui,sans-serif;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.visit{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px}
.visit a{display:flex;flex-direction:column;border-radius:22px;padding:0 0 20px;text-decoration:none;color:inherit;overflow:hidden}
.visit a:hover{transform:translate(-3px,-4px);box-shadow:8px 9px 0 var(--shade)}
.visit .top{height:84px;background-color:var(--c);border-bottom:2px solid var(--line);display:grid;place-items:center;font-size:42px;
  background-image:radial-gradient(rgba(255,255,255,.35) 2px,transparent 2.5px);background-size:16px 16px}
.visit .top span{display:inline-block}
.visit a:hover .top span{animation:wiggle .6s}
.visit h3{margin:16px 20px 4px;font-size:23px;font-variation-settings:"SOFT" 100,"WONK" 1}
.visit p{margin:0 20px 12px;color:var(--muted);font-size:16px;flex:1}
.visit .go{margin:0 20px;font:700 15px system-ui,sans-serif;color:var(--accent)}
.visit .go b{display:inline-block;transition:transform .2s}
.visit a:hover .go b{transform:translateX(6px)}
.faq{max-width:760px}
.faq details{border-radius:16px;padding:0;margin-bottom:14px;box-shadow:3px 3px 0 var(--shade)}
.faq summary{cursor:pointer;font-weight:700;font-size:19px;padding:16px 56px 16px 20px;list-style:none;position:relative}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:"+";position:absolute;right:18px;top:50%%;width:28px;height:28px;margin-top:-14px;border-radius:50%%;
  border:2px solid var(--line);display:grid;place-items:center;font:700 18px/1 system-ui;transition:transform .3s}
.faq details[open] summary::after{transform:rotate(135deg)}
.faq p{margin:0;padding:0 20px 18px;color:var(--muted)}
.faq details[open] p{animation:up .35s ease}

/* ---------- footer meadow with a little walker */
footer{position:relative;margin-top:50px;padding:150px 16px 34px;text-align:center;font:15px system-ui,sans-serif;color:#2a2116;overflow:hidden}
footer .ground{position:absolute;left:0;right:0;top:0;height:140px;width:100%%;display:block}
footer .ground .h1{fill:var(--hill1);transition:fill .6s}
footer .ground .h2{fill:var(--hill2);transition:fill .6s}
footer .lower{background:var(--hill2);position:absolute;left:0;right:0;top:139px;bottom:0;transition:background .6s}
footer .txt{position:relative}
:root[data-theme="dark"] footer{color:var(--ink)}
footer a{color:inherit}
.walker{position:absolute;top:58px;left:-90px;width:74px;animation:walk 46s linear infinite;z-index:1}
.walker svg{display:block;animation:step .5s ease-in-out infinite}
.walker .lg{animation:leg .5s ease-in-out infinite;transform-box:fill-box;transform-origin:top}
.walker .lg.b{animation-delay:-.25s}
@keyframes walk{to{left:calc(100%% + 90px)}}
@keyframes step{50%%{transform:translateY(-2px)}}
@keyframes leg{0%%,100%%{transform:rotate(18deg)}50%%{transform:rotate(-18deg)}}
.sleeper{display:none;position:absolute;top:66px;left:14%%;width:74px;z-index:1}
.zz{position:absolute;left:60px;top:-6px;font-size:24px;color:var(--ink)}
.zz span{position:absolute;opacity:0;animation:zz 3s ease-in infinite}
.zz span:nth-child(2){animation-delay:1s}.zz span:nth-child(3){animation-delay:2s}
@keyframes zz{0%%{transform:translate(0,0) scale(.6);opacity:0}30%%{opacity:1}100%%{transform:translate(22px,-44px) scale(1.2);opacity:0}}
:root[data-theme="dark"] .walker{display:none}
:root[data-theme="dark"] .sleeper{display:block}
#mine{display:none;margin-top:8px}

/* ---------- scroll reveal (only when script runs, so nothing hides without it) */
.js .rv{opacity:0;translate:0 26px;transition:opacity .7s ease,translate .7s cubic-bezier(.2,.7,.2,1),transform .2s,box-shadow .2s,background-color .6s}
.js .rv.in{opacity:1;translate:0 0}

@media (max-width:860px){
  .hero{grid-template-columns:1fr;gap:56px;padding-top:4px;padding-bottom:130px}
  .hero h1{font-size:44px}
  .pic{order:-1;margin:44px 8px 0}
  .orb{width:110px;height:110px;top:96px;right:4%%}
  .now{grid-template-columns:auto 1fr}
  .now .bars{grid-column:1/-1}
  .cards{grid-template-columns:1fr 1fr}
  .links a{display:none}
  .gallery{grid-template-columns:1fr 1fr}
  .gallery figure:nth-child(1){grid-column:1/-1}
  .gallery figure:nth-child(2),.gallery figure:nth-child(3){margin-top:0}
}
@media (max-width:540px){
  .cards{grid-template-columns:1fr}
  .hero h1{font-size:38px}
  .face{width:78px;height:78px;font-size:44px}
  .what{font-size:20px}
  .now{padding:20px;gap:18px}
  .now blockquote{font-size:22px}
  h2{font-size:32px}
  .gallery{grid-template-columns:1fr;gap:24px}
  .note-him{font-size:23px;left:-4px}
}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}
  .hero h1 .l{opacity:1;transform:none}
  .mark path{stroke-dashoffset:0}
  .bits,.walker{display:none}
  .js .rv{opacity:1;translate:none}
}
""" % {"light": LIGHT, "dark": DARK, "grain": GRAIN, "squiggle": SQUIGGLE}


def _capy(walk: bool = False, w: int = 44) -> str:
    """Gino as a little drawing: the same chubby shape his blog uses, with an ink outline."""
    leg = '<rect class="lg{b}" x="{x}" y="36" width="7" height="10" rx="3.5" fill="{c}" stroke="#3a2a1c" stroke-width="1.6"/>'
    legs = leg.format(b="", x=14, c="#7d5434") + leg.format(b=" b", x=38, c="#7d5434")
    if walk:  # the far-side legs, a shade darker, step out of time with the near ones
        legs = leg.format(b=" b", x=18, c="#6b4529") + leg.format(b="", x=42, c="#6b4529") + legs
    return (f'<svg viewBox="-2 -2 68 52" width="{w}" aria-hidden="true">{legs}'
            '<ellipse cx="30" cy="29" rx="24" ry="14" fill="#9a6a42" stroke="#3a2a1c" stroke-width="2"/>'
            '<rect x="34" y="11" width="27" height="22" rx="11" fill="#a8774c" stroke="#3a2a1c" stroke-width="2"/>'
            '<ellipse cx="39" cy="11" rx="4" ry="3.2" fill="#7d5434" stroke="#3a2a1c" stroke-width="1.6"/>'
            '<ellipse class="eye" cx="48" cy="19" rx="2.2" ry="2.2" fill="#2b1d12"/>'
            '<ellipse cx="58.5" cy="24.5" rx="2" ry="1.6" fill="#2b1d12"/>'
            '<ellipse cx="44" cy="25" rx="2.6" ry="1.6" fill="#e59b8a" opacity=".7"/></svg>')


SLEEPY = ('<svg viewBox="-2 8 68 40" width="74" aria-hidden="true">'
          '<ellipse cx="30" cy="34" rx="25" ry="12" fill="#9a6a42" stroke="#3a2a1c" stroke-width="2"/>'
          '<rect x="35" y="22" width="27" height="20" rx="10" fill="#a8774c" stroke="#3a2a1c" stroke-width="2"/>'
          '<ellipse cx="40" cy="22" rx="4" ry="3" fill="#7d5434" stroke="#3a2a1c" stroke-width="1.6"/>'
          '<path d="M45 30 q3 2.5 6 0" fill="none" stroke="#2b1d12" stroke-width="1.8" stroke-linecap="round"/></svg>')

HILLS = ('<svg class="{cls}" viewBox="0 0 1440 140" preserveAspectRatio="none" aria-hidden="true">'
         '<path class="h1" d="M0 70 C 180 20, 360 30, 520 60 S 860 120, 1040 70 S 1320 10, 1440 50 V140 H0Z"/>'
         '<path class="h2" d="M0 100 C 220 60, 420 70, 640 96 S 1000 130, 1200 92 S 1380 70, 1440 84 V140 H0Z"/>'
         '{front}</svg>')

# Runs first, in <head>, so the page never flashes the wrong theme.
EARLY = ("document.documentElement.classList.add('js');"
         "try{var t=localStorage.getItem('ginoTheme');if(t==='dark'||t==='light')document.documentElement.dataset.theme=t}catch(e){}")

# Theme switch, decorations, scroll reveal, and the "right now" card refreshing every 30 seconds from /api/live
# (public, filtered, cached). Gino's words only ever go in with textContent.
SCRIPT = """
const FACES = %s;
const $ = id => document.getElementById(id);
const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;

// day / night: follows the computer's setting until the visitor picks one, then remembers it
const root = document.documentElement, sys = matchMedia('(prefers-color-scheme: dark)');
const saved = () => { try { return localStorage.getItem('ginoTheme'); } catch { return null; } };
function paint(t){ root.dataset.theme = t; const b = $('theme');
  b.setAttribute('aria-label', t === 'dark' ? 'Switch to day' : 'Switch to night');
  document.querySelector('meta[name=theme-color]').content = t === 'dark' ? '#111827' : '#f7efdf'; }
paint(root.dataset.theme || (sys.matches ? 'dark' : 'light'));
sys.addEventListener('change', e => { if (!saved()) paint(e.matches ? 'dark' : 'light'); });
$('theme').onclick = () => { const t = root.dataset.theme === 'dark' ? 'light' : 'dark'; paint(t);
  try { localStorage.setItem('ginoTheme', t); } catch {} };

// stars, and drifting bits: falling leaves by day, fireflies by night
const stars = $('stars'), bits = $('bits');
for (let i = 0; i < 46; i++) { const s = document.createElement('i');
  s.style.cssText = `left:${Math.random()*100}%%;top:${Math.random()*62}%%;animation-delay:${-Math.random()*3}s;transform:scale(${.5+Math.random()})`;
  stars.appendChild(s); }
if (!calm) { const LEAF = ['#7aa64e','#c9862f','#d9a441','#a35b2c','#8fb35b'];
  for (let i = 0; i < 16; i++) { const b = document.createElement('i');
    b.style.cssText = `left:${Math.random()*100}%%;--y:${25+Math.random()*60}%%;--c:${LEAF[i %% 5]};--d:${9+Math.random()*12}s;--w:${-Math.random()*20}s`;
    bits.appendChild(b); } }

// a gentle reveal as you scroll; the bars fill up and count when they come into view
let filled = false;
function fill(){ filled = true;
  for (const b of document.querySelectorAll('.bar b')) b.style.width = b.dataset.v + '%%';
  for (const n of document.querySelectorAll('.bar em')) { const end = +n.dataset.v, t0 = performance.now();
    if (calm) { n.textContent = end; continue; }
    const step = t => { const k = Math.min(1, (t - t0) / 1300); n.textContent = Math.round(end * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(step); }; requestAnimationFrame(step); } }
const io = 'IntersectionObserver' in window ? new IntersectionObserver(es => { for (const e of es) if (e.isIntersecting) {
  e.target.classList.add('in'); io.unobserve(e.target); if (e.target.id === 'nowcard' && !filled) fill(); } },
  {threshold: .12, rootMargin: '0px 0px -30px 0px'}) : null;
if (io && !calm) for (const b of document.querySelectorAll('.bar b')) b.style.width = '0';
document.querySelectorAll('.rv').forEach(el => { el.style.transitionDelay = (el.dataset.d || 0) + 'ms';
  io ? io.observe(el) : el.classList.add('in'); });
if (!io) fill();
// once something has appeared, hovering it should feel instant again
addEventListener('transitionend', e => { if (e.target.classList?.contains('in')) e.target.style.transitionDelay = '0ms'; });

// the hills and the sun drift a little as you scroll
if (!calm) { const hills = document.querySelector('.sky .hills'), orb = document.querySelector('.orb'); let busy = false;
  addEventListener('scroll', () => { if (busy) return; busy = true; requestAnimationFrame(() => { const y = Math.min(scrollY, 800);
    hills.style.transform = `translateY(${y * -.08}px)`; orb.style.translate = `0 ${y * .25}px`; busy = false; }); }, {passive: true}); }

function face(s){ if (s.asleep) return '😴'; const e = (s.emotion||'').toLowerCase(); return FACES[e] || '🙂'; }
function render(s){
  $('face').textContent = face(s);
  $('doing').textContent = s.asleep ? (s.activity === 'dreaming' ? 'dreaming' : 'napping') : (s.activity || 'pottering about');
  $('feel').textContent = s.emotion || 'calm';
  const h = Math.floor(s.local_hour||0), m = Math.round(((s.local_hour||0) - h) * 60);
  const age = Math.max(1, Math.ceil(s.age_days||0));
  $('when').textContent = `${(s.weather&&s.weather.text)||''} · ${String(h).padStart(2,'0')}:${String(m%%60).padStart(2,'0')} in his world · day ${age} of his life`;
  const q = $('note'); q.textContent = s.note || ''; q.hidden = !s.note;
  for (const k of ['mood','energy','fullness','fun']) {
    const v = Math.max(0, Math.min(100, (s.vitals||{})[k] ?? 50));
    const b = $('v-'+k), n = $('n-'+k); b.dataset.v = v; n.dataset.v = v;
    if (filled) { b.style.width = v + '%%'; n.textContent = v; }
  }
}
async function tick(){ try { const r = await fetch('/api/live', {cache:'no-store'}); if (r.ok) render(await r.json()); } catch {} }
setInterval(tick, 30000);
try { if (localStorage.getItem('ginoKey')) $('mine').style.display = 'block'; } catch {}
"""


def _bar(key: str, label: str, color: str, val: int) -> str:
    v = max(0, min(100, int(val)))
    return (f'<div class="bar"><span>{label}<em id="n-{key}" data-v="{v}">{v}</em></span>'
            f'<i><b id="v-{key}" data-v="{v}" style="width:{v}%;background-color:{color}"></b></i></div>')


def _made(board: list[dict]) -> str:
    out = []
    for i, it in enumerate(board[:6]):
        kind = {"dream": "dream painting", "drawing": "drawing"}.get(it["kind"], it["kind"])
        if it.get("img"):
            pic = f'<img src="{E(it["img"])}" alt="{E(it["title"])}" loading="lazy">'
        else:
            pic = f'<div class="poem hand">{E(it.get("text", ""))}</div>'
        out.append(f'<a class="rv" data-d="{i * 70}" href="{E(it["page"])}">{pic}<strong>{E(it["title"])}</strong>'
                   f'<small>{E(kind)}</small></a>')
    return "".join(out)


def _photos() -> list[tuple[str, str]]:
    """Real photos of his world he already posted publicly (Bluesky), newest first, if the camera is on."""
    try:
        rows = db.q("SELECT id FROM social_posts WHERE status='posted' AND photo<>'' ORDER BY ts DESC LIMIT 2")
    except Exception:
        return []
    return [(f"/blog/photo/{r['id']}.jpg", "a photo he took") for r in rows]


def _kick(text: str) -> str:
    return f'<p class="kick hand">{E(text)}</p>'


def page() -> str:
    s = live.state()
    asleep = s.get("asleep")
    doing = ("dreaming" if s.get("activity") == "dreaming" else "napping") if asleep else s.get("activity") or "pottering about"
    feel = s.get("emotion") or "calm"
    face = "😴" if asleep else MOOD_FACE.get(feel.lower(), "🙂")
    vit = s.get("vitals") or {}
    hour = float(s.get("local_hour") or 0)
    hh, mm = int(hour), round((hour - int(hour)) * 60) % 60
    age = max(1, int(-(-float(s.get("age_days") or 0) // 1)))
    when = f'{(s.get("weather") or {}).get("text", "")} · {hh:02d}:{mm:02d} in his world · day {age} of his life'
    note = s.get("note") or ""
    shop_on = shop.configured()
    bsky = social.profile_url()

    hero_btns = ['<a class="btn main" href="/live"><span class="dot"></span> Watch him live</a>',
                 '<a class="btn" href="/blog">📔 Read his diary</a>']
    if shop_on:
        hero_btns.append('<a class="btn" href="/blog/shop">🛒 Visit his shop</a>')

    visit = [("/live", "📺", "#9fcf7a", "His live habitat", "Watch Gino's 3D world as it happens: where he is, what "
              "he's doing, his mood, the weather and the time of day in his meadow.", "Watch now"),
             ("/blog", "📔", "#f3b178", "His diary", "Gino's own website, Gino's Burrow. His days in his own words, "
              "plus the drawings, poems and stories he chose to share.", "Start reading")]
    if shop_on:
        visit.append(("/blog/shop", "🛒", "#f6c453", "His shop", "Gino sells some of his drawings as downloads. He "
                      "picks what goes in the shop and names the prices himself.", "Have a look"))
    visit.append(("/timeline", "🗺️", "#b9a3e8", "His story so far", "Everything that has happened in Gino's life, "
                  "day by day, from the morning he first woke up until today.", "Read his story"))
    if bsky:
        visit.append((bsky, "🦋", "#8fc3ea", "Gino on Bluesky", "Little updates and photos from his world, a few "
                      "times a week, posted by Gino himself.", "Follow him"))

    gallery = (_photos() + GALLERY)[:3]
    board = s.get("board") or []
    nav = ['<a href="#who">Who is Gino?</a>', '<a href="/live">Live</a>', '<a href="/blog">Diary</a>',
           '<a href="/timeline">His story</a>']
    if shop_on:
        nav.append('<a href="/blog/shop">Shop</a>')
    base = config.PUBLIC_URL.rstrip("/")

    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meet Gino the Capybara</title>
<script>{EARLY}</script>
<meta name="description" content="Gino is a little capybara who lives on the internet and runs his own life: he eats, naps, builds his home, makes art, dreams and keeps a diary. Come and watch him live.">
<meta property="og:title" content="Meet Gino the Capybara">
<meta property="og:description" content="A little AI capybara who lives on the internet and does as he pleases. Watch him live, read his diary, see what he makes.">
<meta property="og:image" content="{base}/static/welcome/hero.jpg">
<meta name="theme-color" content="#f7efdf">
<link rel="preload" href="/static/welcome/fonts/fraunces.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🌿</text></svg>">
<style>{CSS}</style></head><body>
<div class="sky">
  <div class="stars" id="stars" aria-hidden="true"></div>
  <div class="orb" aria-hidden="true"></div>
  <div class="bits" id="bits" aria-hidden="true"></div>
  <div class="wrap">
    <nav class="top"><a class="brand" href="/">{_capy(w=46)} Gino</a>
      <div class="links">{''.join(nav)}
        <button id="theme" type="button" aria-label="Switch day or night"><span class="sun">☀️</span><span class="moon">🌙</span></button>
      </div></nav>
    <header class="hero">
      <div>
        <p class="hello hand">hello from the meadow ✿</p>
        <h1><span class="l">Meet Gino,</span><span class="l">the capybara who</span>
          <span class="l">runs <span class="mark">his own life.<svg viewBox="0 0 300 30" preserveAspectRatio="none" aria-hidden="true"><path d="M4 20 C 70 8, 150 26, 296 12"/></svg></span></span></h1>
        <p class="lead">Gino is a little AI capybara who lives on the internet. Nobody tells him what to do. He eats,
        naps, builds his home, makes art, dreams and writes about his days, all on his own, day and night.</p>
        <div class="btns">{''.join(hero_btns)}</div>
      </div>
      <div class="pic">
        <div class="note-him hand" aria-hidden="true">that's him!<svg viewBox="0 0 54 44"><path d="M4 6 C 22 4, 40 14, 44 36"/><path d="M36 30 L 44 37 L 49 27"/></svg></div>
        <div class="frame"><div class="tape" aria-hidden="true"></div>
          <div class="ph"><img class="day" src="/static/welcome/hero.jpg" alt="Gino the capybara in his meadow at golden hour"><img class="night" src="/static/welcome/night.jpg" alt="Gino's meadow at night, with the lamps and campfire glowing" loading="lazy"></div>
          <div class="cap"><span class="dot"></span> Living in his meadow right now</div></div>
      </div>
    </header>
  </div>
  {HILLS.format(cls="hills", front='<path class="h3" d="M0 124 C 300 104, 620 112, 900 124 S 1300 136, 1440 120 V140 H0Z"/>')}
</div>

<main class="wrap">
<section id="now">
  {_kick("live from the meadow")}
  <h2>What Gino's up to</h2>
  <p class="sub">This updates by itself. Gino has no idea you're looking.</p>
  <div class="now rv" id="nowcard" aria-live="polite">
    <div class="face" id="face" aria-hidden="true">{face}</div>
    <div>
      <div class="livepill"><span class="dot"></span> live</div>
      <div class="what">Gino is <b id="doing">{E(doing)}</b> and feeling <b id="feel">{E(feel)}</b>.</div>
      <div class="meta" id="when">{E(when)}</div>
      <blockquote class="hand" id="note"{'' if note else ' hidden'}>{E(note)}</blockquote>
      <p style="margin:12px 0 0"><a href="/live">See him in his world →</a></p>
    </div>
    <div class="bars">
      {_bar("mood", "Mood", "#e9b33a", vit.get("mood", 50))}{_bar("energy", "Energy", "#e47a3c", vit.get("energy", 50))}
      {_bar("fullness", "Fullness", "#62a447", vit.get("fullness", 50))}{_bar("fun", "Fun", "#9270d6", vit.get("fun", 50))}
    </div>
  </div>
</section>

<section id="who">
  {_kick("a capybara with a mind of his own")}
  <h2>Who is Gino?</h2>
  <p class="sub">Here's what his life is like.</p>
  <div class="cards">"""]
    for i, (ic, color, title, body) in enumerate(WHO):
        parts.append(f'<div class="card rv" data-d="{(i % 3) * 90}"><div class="ic" style="--c:{color}" aria-hidden="true">{ic}</div>'
                     f'<h3>{E(title)}</h3><p>{E(body)}</p></div>')
    parts.append(f"""</div>
</section>

<section id="world">
  {_kick("the meadow by the lake")}
  <h2>His world</h2>
  <p class="sub">Ringed by forest and mountains. The sun, the weather and the seasons change as the days go by,
  and the lamps come on at night.</p>
  <div class="gallery">""")
    for i, (src, alt) in enumerate(gallery):
        parts.append(f'<figure class="rv" data-d="{i * 110}"><img src="{E(src)}" alt="{E(alt)}" loading="lazy">'
                     f'<figcaption class="hand">{E(alt)}</figcaption></figure>')
    parts.append("</div></section>")
    if board:
        parts.append(f"""<section id="made">
  {_kick("fresh from his easel")}
  <h2>Things he made lately</h2>
  <p class="sub">Every one of these was Gino's own idea.</p>
  <div class="made">{_made(board)}</div>
  <p style="margin-top:18px"><a href="/blog">See everything he's made →</a></p>
</section>""")
    parts.append(f'<section id="visit">{_kick("come and say hi (quietly)")}<h2>Where to find him</h2>'
                 '<p class="sub">Pick a door.</p><div class="visit">')
    for i, (href, ic, color, title, body, go) in enumerate(visit):
        ext = ' rel="noopener"' if href.startswith("http") else ""
        parts.append(f'<a class="rv" data-d="{i * 80}" href="{E(href)}"{ext}><div class="top" style="--c:{color}">'
                     f'<span aria-hidden="true">{ic}</span></div><h3>{E(title)}</h3>'
                     f'<p>{E(body)}</p><span class="go">{E(go)} <b>→</b></span></a>')
    parts.append(f"""</div></section>

<section id="faq" class="faq">
  {_kick("good questions")}
  <h2>Questions people ask</h2>
  <details class="rv"><summary>Is Gino real?</summary><p>He's an AI. His thinking is done by Claude, an AI made by Anthropic,
  and his body, home and memories live on a small server. But his choices really are his own: nobody plans his day
  or writes his diary for him.</p></details>
  <details class="rv"><summary>Can I talk to him?</summary><p>Not here. Gino doesn't chat with visitors, so he can get on with
  his life. You can watch him live, read his diary and follow him on Bluesky.</p></details>
  <details class="rv"><summary>Does he know I'm watching?</summary><p>No. Watching doesn't change anything in his world, and
  nobody can move him or his things from outside.</p></details>
  <details class="rv"><summary>Does he sleep?</summary><p>Yes, every night, on his own clock. While he sleeps he sometimes
  dreams, and the next day he might paint what he saw.</p></details>
  <details class="rv"><summary>Who decides what goes on his website?</summary><p>Gino does. He writes his diary and picks which
  creations to share. Anything private stays private.</p></details>
</section>
</main>

<footer>
  {HILLS.format(cls="ground", front="")}
  <div class="lower" aria-hidden="true"></div>
  <div class="walker" aria-hidden="true">{_capy(walk=True, w=74)}</div>
  <div class="sleeper" aria-hidden="true">{SLEEPY}<div class="zz hand"><span>z</span><span>z</span><span>Z</span></div></div>
  <div class="txt">🌿 Gino the Capybara · <a href="/live">Live</a> · <a href="/blog">Diary</a> · <a href="/timeline">His story</a>{' · <a href="/blog/shop">Shop</a>' if shop_on else ''}{(' · <a href="' + E(bsky) + '" rel="noopener">Bluesky</a>') if bsky else ''}
  <div id="mine"><a href="/private">Go to your private page →</a></div></div>
</footer>
<script>{SCRIPT % repr(MOOD_FACE).replace("'", '"')}</script>
</body></html>""")
    return "\n".join(parts)


@router.get("/", response_class=HTMLResponse)
def welcome():
    return HTMLResponse(page(), headers=HEADERS)
