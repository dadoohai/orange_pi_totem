#!/usr/bin/env bash
set -eu

APP_USER="totem"
MEDIA_GROUPS="video render audio"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "ERROR: user not found: $APP_USER" >&2
  exit 1
fi

echo "Before:"
id "$APP_USER"
groups "$APP_USER"

echo
for group in $MEDIA_GROUPS; do
  if ! getent group "$group" >/dev/null 2>&1; then
    echo "WARN: group does not exist, skipping: $group" >&2
    continue
  fi

  if id -nG "$APP_USER" | tr ' ' '\n' | grep -Fx "$group" >/dev/null 2>&1; then
    echo "OK: $APP_USER already belongs to $group"
  else
    usermod -a -G "$group" "$APP_USER"
    echo "OK: added $APP_USER to $group"
  fi
done

echo
echo "After:"
id "$APP_USER"
groups "$APP_USER"
