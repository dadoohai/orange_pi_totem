#!/usr/bin/env bash
set -eu

APP_USER="totem"
APP_GROUP="totem"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

if [ -x /usr/sbin/nologin ]; then
  NOLOGIN_SHELL="/usr/sbin/nologin"
elif [ -x /sbin/nologin ]; then
  NOLOGIN_SHELL="/sbin/nologin"
else
  echo "ERROR: nologin shell not found." >&2
  exit 1
fi

if getent group "$APP_GROUP" >/dev/null; then
  echo "Group exists: $APP_GROUP"
else
  groupadd --system "$APP_GROUP"
  echo "Group created: $APP_GROUP"
fi

if id "$APP_USER" >/dev/null 2>&1; then
  echo "User exists: $APP_USER"
  CURRENT_SHELL="$(getent passwd "$APP_USER" | awk -F: '{print $7}')"
  if [ "$CURRENT_SHELL" != "$NOLOGIN_SHELL" ]; then
    echo "WARN: existing user shell is $CURRENT_SHELL, expected $NOLOGIN_SHELL. Not modifying existing user." >&2
  fi
else
  useradd \
    --system \
    --gid "$APP_GROUP" \
    --home-dir /nonexistent \
    --no-create-home \
    --shell "$NOLOGIN_SHELL" \
    "$APP_USER"
  passwd -l "$APP_USER" >/dev/null 2>&1 || true
  echo "User created: $APP_USER"
fi

echo
getent passwd "$APP_USER"
getent group "$APP_GROUP"
