#!/usr/bin/env bash
# Gino's one-command home on a fresh Ubuntu server (made for a Hetzner Cloud server, Ubuntu 24.04).
#
#   curl -fsSL https://raw.githubusercontent.com/rauulglez16-max/Gino-the-Capybara/main/deploy/install.sh | bash
#
# Optional settings, put in front of `bash` (VAR=value bash):
#   ANTHROPIC_API_KEY   Gino's Claude key (asked for if you're at a keyboard; can be added later with `gino set-key`)
#   GINO_PASSWORD       password for Gino's page (one is made up for you if you leave it out)
#   GITHUB_TOKEN        only if the GitHub repo is private: a read-only token for it
#   GINO_DAD_NAME, GINO_TZ, GINO_MODEL, GINO_DAILY_BUDGET_USD   same as in .env.example
#   GINO_BRANCH         which branch to follow for updates (default: main)
#   GINO_DOMAIN         your own web address, if you have one (default: a free <ip>.sslip.io address)
#
# Safe to run again: it keeps Gino's memories and settings and just repairs/refreshes everything else.
set -euo pipefail

main() {
  umask 022
  REPO="${GINO_REPO:-rauulglez16-max/Gino-the-Capybara}"
  BRANCH="${GINO_BRANCH:-main}"
  BASE=/opt/gino
  APP="$BASE/app"
  ENV_FILE=/etc/gino/gino.env

  as_gino() { HOME=/opt/gino setpriv --reuid=gino --regid=gino --init-groups -- "$@"; }
  say() { printf '\n\033[1;32m🌿 %s\033[0m\n' "$*"; }
  die() { printf '\n\033[1;31m✋ %s\033[0m\n' "$*" >&2; exit 1; }
  ask() {  # ask "question" -> answer on stdout, empty when nobody is at a keyboard
    local a=""
    if { true </dev/tty; } 2>/dev/null; then read -r -p "$1" a </dev/tty || true; fi
    printf '%s' "$a"
  }

  [ "$(id -u)" -eq 0 ] || die "Please run this as root (on Hetzner you log in as root, or put sudo in front of bash)."
  command -v apt-get >/dev/null || die "This installer needs Ubuntu or Debian."

  say "Installing what Gino needs (1-3 minutes)..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq git python3 python3-venv curl ca-certificates caddy ufw >/dev/null

  id gino >/dev/null 2>&1 || useradd --system --home-dir "$BASE" --shell /usr/sbin/nologin gino
  mkdir -p "$BASE/data" "$BASE/backups" /etc/gino /var/lib/gino-deploy
  chown gino:gino "$BASE" "$BASE/data"
  chmod 700 "$BASE/data" "$BASE/backups"

  # --- the code ---
  local url="${GINO_REPO_URL:-https://github.com/$REPO.git}"
  if [ ! -d "$APP/.git" ]; then
    say "Downloading Gino from GitHub..."
    if [ -n "${GITHUB_TOKEN:-}" ]; then
      url="https://x-access-token:${GITHUB_TOKEN}@github.com/$REPO.git"
    fi
    as_gino git clone --quiet --branch "$BRANCH" "$url" "$APP" \
      || die "Couldn't download Gino. If the repo is private, add GITHUB_TOKEN=... in front of bash (see deploy/README.md)."
  elif [ -n "${GITHUB_TOKEN:-}" ]; then
    as_gino git -C "$APP" remote set-url origin "https://x-access-token:${GITHUB_TOKEN}@github.com/$REPO.git"
  fi
  printf '%s\n' "$BRANCH" > /var/lib/gino-deploy/branch

  say "Setting up Python..."
  [ -x "$BASE/venv/bin/python" ] || python3 -m venv "$BASE/venv"
  "$BASE/venv/bin/pip" install -q --upgrade pip
  "$BASE/venv/bin/pip" install -q -r "$APP/requirements.txt"

  # --- settings (kept if they already exist) ---
  if [ ! -f "$ENV_FILE" ]; then
    local key="${ANTHROPIC_API_KEY:-}"
    if [ -z "$key" ]; then
      key="$(ask $'\nPaste your Claude API key (starts with sk-ant-), or just press Enter to add it later: ')"
    fi
    local password="${GINO_PASSWORD:-}"
    if [ -z "$password" ]; then
      password="$(tr -dc 'a-km-z2-9' </dev/urandom | head -c 16 || true)"
    fi
    umask 027
    cat > "$ENV_FILE" <<EOF
# Gino's settings on this server. Change one with:  nano $ENV_FILE   then:  gino restart
ANTHROPIC_API_KEY=$key
GINO_PASSWORD=$password
GINO_DAD_NAME=${GINO_DAD_NAME:-Raul}
GINO_TZ=${GINO_TZ:-Europe/London}
GINO_HEMISPHERE=${GINO_HEMISPHERE:-north}
GINO_MODEL=${GINO_MODEL:-claude-opus-5-5}
GINO_DAILY_BUDGET_USD=${GINO_DAILY_BUDGET_USD:-3}
GINO_EFFORT=${GINO_EFFORT:-medium}
GINO_WEB=${GINO_WEB:-1}

# Server plumbing, no need to touch
GINO_HOST=127.0.0.1
GINO_PORT=8787
GINO_DATA_DIR=$BASE/data
EOF
    umask 022
  fi
  chown root:gino "$ENV_FILE"
  chmod 640 "$ENV_FILE"

  # --- services: Gino himself + the 5-minute update check ---
  install -m 644 "$APP"/deploy/systemd/gino.service "$APP"/deploy/systemd/gino-update.service \
    "$APP"/deploy/systemd/gino-update.timer /etc/systemd/system/
  ln -sf "$APP/deploy/gino" /usr/local/bin/gino
  chmod +x "$APP/deploy/gino"
  systemctl daemon-reload
  systemctl enable --now gino-update.timer >/dev/null
  systemctl enable gino >/dev/null
  systemctl restart gino

  # --- a web address with a padlock (https), via Caddy ---
  local ip domain
  ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<NF;i++) if($i=="src") print $(i+1)}' | head -1)"
  [ -n "$ip" ] || ip="$(curl -4 -fsS --max-time 5 https://api.ipify.org || true)"
  domain="${GINO_DOMAIN:-${ip//./-}.sslip.io}"
  printf '%s\n' "$domain" > /var/lib/gino-deploy/domain
  cat > /etc/caddy/Caddyfile <<EOF
# Gino's front door. Caddy gets and renews the https certificate by itself.
$domain {
	encode gzip
	reverse_proxy 127.0.0.1:8787
}
EOF
  systemctl enable caddy >/dev/null
  systemctl restart caddy

  # --- firewall: only ssh and the website get in ---
  ufw allow 22/tcp >/dev/null
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null

  # --- wait for Gino to wake up ---
  local ok=""
  for _ in $(seq 1 30); do
    if curl -fsS -o /dev/null --max-time 3 http://127.0.0.1:8787/; then ok=1; break; fi
    sleep 2
  done
  [ -n "$ok" ] || die "Gino didn't wake up. See what happened with:  gino logs"

  say "Gino is home! 🎉"
  printf '\n   Visit him:   https://%s\n' "$domain"
  printf '   Password:    %s   (write this down; see it again any time with: gino password)\n' \
    "$(grep -m1 '^GINO_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
  if ! grep -q '^ANTHROPIC_API_KEY=.\+' "$ENV_FILE"; then
    printf '\n   He is on his practice brain for now. Give him his real one with:  gino set-key\n'
  fi
  printf '\n   The padlock address can take a minute or two to start working the very first time.\n'
  printf '   New code on GitHub (%s) reaches him within about 5 minutes, and his memories stay put.\n' "$BRANCH"
  printf '   Handy commands: gino status | gino logs | gino restart | gino update | gino backup\n\n'
}

main "$@"
