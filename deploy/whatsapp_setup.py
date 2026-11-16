"""Helper for `gino whatsapp`. Only needs plain Python. Settings come from environment variables (never the
command line, so secrets don't show in the process list).

  check   make sure the token and Phone number ID work, and say which number Gino has
  test    send dad the template message (works even outside WhatsApp's 24-hour window)
"""
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("WHATSAPP_API", "https://graph.facebook.com/v26.0").rstrip("/")
TOKEN = os.environ.get("WHATSAPP_TOKEN", "").strip()
PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "").strip()
TO = "".join(c for c in os.environ.get("WHATSAPP_TO", "") if c.isdigit())
TEMPLATE = os.environ.get("WHATSAPP_TEMPLATE", "") or "hello_world"
LANG = os.environ.get("WHATSAPP_TEMPLATE_LANG", "") or "en_US"


def call(path, payload=None):
    req = urllib.request.Request(f"{API}/{path}", data=json.dumps(payload).encode() if payload else None,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        try:
            return None, json.loads(e.read().decode()).get("error", {}).get("message", f"HTTP {e.code}")
        except Exception:
            return None, f"HTTP {e.code}"
    except (urllib.error.URLError, OSError) as e:
        return None, f"couldn't reach Meta ({type(e).__name__})"


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "check"
    if what == "check":
        if not PHONE_ID.isdigit():
            sys.exit("The Phone number ID should be only digits (it's under WhatsApp > API Setup).")
        if not 8 <= len(TO) <= 15:
            sys.exit("Your number should include the country code, like 447700900123 for a UK mobile.")
        info, err = call(f"{PHONE_ID}?fields=display_phone_number,verified_name")
        if not info:
            sys.exit(f"Meta didn't accept that token or Phone number ID: {err}")
        print(f"✅ Gino's WhatsApp number: {info.get('display_phone_number', '?')} ({info.get('verified_name', '')})")
    elif what == "test":
        _, err = call(f"{PHONE_ID}/messages", {"messaging_product": "whatsapp", "to": TO, "type": "template",
                                               "template": {"name": TEMPLATE, "language": {"code": LANG}}})
        if err:
            sys.exit(f"That didn't work: {err}")
        print("Sent! Check WhatsApp on your phone. 📱 Reply \"hi\" so Gino can text you freely for the next day.")
    else:
        sys.exit("usage: whatsapp_setup.py check|test")


if __name__ == "__main__":
    main()
