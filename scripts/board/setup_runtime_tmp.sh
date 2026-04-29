#!/usr/bin/env bash
set -eu

APP_USER="totem"
APP_GROUP="totem"
RUNTIME_DIR="/tmp/kiosky"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "ERROR: user not found: $APP_USER" >&2
  exit 1
fi

if ! getent group "$APP_GROUP" >/dev/null 2>&1; then
  echo "ERROR: group not found: $APP_GROUP" >&2
  exit 1
fi

show_state() {
  local label="$1"

  echo "$label:"
  if [ -e "$RUNTIME_DIR" ]; then
    stat -c '%A %U %G %n' "$RUNTIME_DIR"
  else
    echo "$RUNTIME_DIR does not exist"
  fi
}

show_state "Before"

install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" "$RUNTIME_DIR"
chmod 0750 "$RUNTIME_DIR"
chown "$APP_USER:$APP_GROUP" "$RUNTIME_DIR"

echo
show_state "After"
