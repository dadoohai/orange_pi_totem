#!/usr/bin/env bash
set -eu

APP_USER="totem"
APP_GROUP="totem"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "ERROR: user not found: $APP_USER. Run setup_totem_user.sh first." >&2
  exit 1
fi

if ! getent group "$APP_GROUP" >/dev/null; then
  echo "ERROR: group not found: $APP_GROUP. Run setup_totem_user.sh first." >&2
  exit 1
fi

echo "Before:"
for path in \
  /opt/totem \
  /opt/totem/kiosky-player \
  /opt/totem/venv \
  /data/config \
  /data/media/kiosky-player \
  /data/state/kiosky-player \
  /data/spool/kiosky-player \
  /data/logs/kiosky-player \
  /tmp/kiosky
do
  if [ -e "$path" ]; then
    stat -c '%A %U %G %n' "$path"
  else
    echo "missing $path"
  fi
done | sort

install -d -m 0755 -o root -g root /opt/totem
install -d -m 0755 -o root -g root /opt/totem/kiosky-player
install -d -m 0755 -o root -g root /opt/totem/venv

install -d -m 0755 -o root -g root /data
install -d -m 0755 -o root -g root /data/media
install -d -m 0755 -o root -g root /data/state
install -d -m 0755 -o root -g root /data/spool
install -d -m 0755 -o root -g root /data/logs

install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" /data/config
install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" /data/media/kiosky-player
install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" /data/state/kiosky-player
install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" /data/spool/kiosky-player
install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" /data/logs/kiosky-player
install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" /tmp/kiosky

echo
echo "After:"
for path in \
  /opt/totem \
  /opt/totem/kiosky-player \
  /opt/totem/venv \
  /data/config \
  /data/media/kiosky-player \
  /data/state/kiosky-player \
  /data/spool/kiosky-player \
  /data/logs/kiosky-player \
  /tmp/kiosky
do
  stat -c '%A %U %G %n' "$path"
done | sort
