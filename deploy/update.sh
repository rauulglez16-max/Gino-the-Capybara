#!/usr/bin/env bash
# Runs every 5 minutes (gino-update.timer). If GitHub has new code, back Gino up, switch to it and restart him.
# If the new version won't start, go back to the one that worked and skip that version until something newer lands.
# Gino's memories live in /opt/gino/data, outside the code folder, so updates never touch them.
#
# Everything is inside main() so bash reads the whole file before running it: this script can safely update itself.
set -euo pipefail

as_gino() { HOME=/opt/gino setpriv --reuid=gino --regid=gino --init-groups -- "$@"; }

main() {
  local BASE=/opt/gino APP=/opt/gino/app STATE=/var/lib/gino-deploy
  local BRANCH force="${1:-}"
  BRANCH="$(cat "$STATE/branch" 2>/dev/null || echo main)"
  mkdir -p "$STATE"

  exec 9>"$STATE/lock"
  flock -n 9 || { echo "Another update is already running."; return 0; }

  g() { as_gino git -C "$APP" "$@"; }
  healthy() {
    for _ in $(seq 1 30); do
      sleep 2
      systemctl is-active --quiet gino && curl -fsS -o /dev/null --max-time 3 http://127.0.0.1:8787/ && return 0
    done
    return 1
  }

  backup_now "$BASE" daily

  g fetch --quiet origin "$BRANCH"
  local current new
  current="$(g rev-parse HEAD)"
  new="$(g rev-parse "origin/$BRANCH")"

  if [ "$current" = "$new" ]; then
    [ "$force" = "--verbose" ] && echo "Gino is already on the newest version (${current:0:7})."
    return 0
  fi
  if [ "$new" = "$(cat "$STATE/bad-commit" 2>/dev/null)" ] && [ "$force" != "--verbose" ]; then
    return 0  # this version already failed to start; wait for a newer one
  fi

  echo "New version ${new:0:7} found (was ${current:0:7}). Backing up and updating..."
  backup_now "$BASE" before-update

  apply "$new" "$current"
  if healthy; then
    rm -f "$STATE/bad-commit"
    echo "Gino updated to ${new:0:7}: $(g log -1 --format=%s)"
    return 0
  fi

  echo "Version ${new:0:7} didn't start. Going back to ${current:0:7}." >&2
  journalctl -u gino -n 30 --no-pager >&2 || true
  echo "$new" > "$STATE/bad-commit"
  apply "$current" "$new"
  healthy || echo "Gino still isn't healthy after going back. Check: gino logs" >&2
  return 1
}

apply() {  # apply <commit> <previous commit>: put that code in place and restart Gino
  local target="$1" previous="$2" APP=/opt/gino/app BASE=/opt/gino
  as_gino git -C "$APP" reset --quiet --hard "$target"
  if ! as_gino git -C "$APP" diff --quiet "$previous" "$target" -- requirements.txt; then
    "$BASE/venv/bin/pip" install -q -r "$APP/requirements.txt"
  fi
  # Pick up changes to the service files themselves
  local f changed=""
  for f in gino.service gino-update.service gino-update.timer; do
    if ! cmp -s "$APP/deploy/systemd/$f" "/etc/systemd/system/$f"; then
      install -m 644 "$APP/deploy/systemd/$f" /etc/systemd/system/
      changed=1
    fi
  done
  [ -n "$changed" ] && systemctl daemon-reload
  chmod +x "$APP/deploy/gino"
  systemctl restart gino
}

backup_now() {  # backup_now <base> daily|before-update|manual
  local BASE="$1" kind="$2" dest="$1/backups" stamp tmp
  [ -f "$BASE/data/gino.db" ] || return 0
  if [ "$kind" = daily ] && ls "$dest"/gino-"$(date +%F)"-* >/dev/null 2>&1; then
    return 0  # already have one from today
  fi
  stamp="$(date +%F-%H%M%S)"
  tmp="$(mktemp -d)"
  # SQLite's own backup copies a consistent snapshot even while Gino is writing
  "$BASE/venv/bin/python" - "$BASE/data/gino.db" "$tmp/gino.db" <<'PY'
import sqlite3, sys
src, dst = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
PY
  [ -d "$BASE/data/creations" ] && cp -a "$BASE/data/creations" "$tmp/"
  tar -czf "$dest/gino-$stamp-$kind.tar.gz" -C "$tmp" .
  rm -rf "$tmp"
  chmod 600 "$dest/gino-$stamp-$kind.tar.gz"
  # keep the newest 20 backups
  # shellcheck disable=SC2012  # our own file names, no spaces
  ls -1t "$dest"/gino-*.tar.gz 2>/dev/null | tail -n +21 | xargs -r rm -f
  echo "Backup saved: $dest/gino-$stamp-$kind.tar.gz"
}

if [ "${1:-}" = "--backup-only" ]; then
  backup_now /opt/gino manual
else
  main "$@"
fi
