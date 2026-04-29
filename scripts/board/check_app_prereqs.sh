#!/usr/bin/env bash
set -eu

APP_USER="totem"
APP_GROUP="totem"
APP_MEDIA_DIR="/data/media/kiosky-player"

failures=0

ok() {
  echo "OK: $*"
}

warn() {
  echo "WARN: $*" >&2
}

fail() {
  echo "ERROR: $*" >&2
  failures=$((failures + 1))
}

check_command() {
  command -v "$1" >/dev/null 2>&1
}

check_path() {
  path="$1"
  expected_owner="$2"
  expected_group="$3"

  if [ ! -d "$path" ]; then
    fail "directory missing: $path"
    return
  fi

  owner="$(stat -c '%U' "$path")"
  group="$(stat -c '%G' "$path")"
  mode="$(stat -c '%A' "$path")"

  if [ "$owner" = "$expected_owner" ] && [ "$group" = "$expected_group" ]; then
    ok "$path owner=$owner group=$group mode=$mode"
  else
    fail "$path owner/group is $owner:$group, expected $expected_owner:$expected_group"
  fi
}

check_user_writable_dir() {
  path="$1"
  if [ ! -d "$path" ]; then
    fail "directory missing: $path"
    return
  fi

  if check_command runuser; then
    if runuser -u "$APP_USER" -- sh -c 'test -w "$1" && test -x "$1"' sh "$path"; then
      ok "$path is writable by $APP_USER"
    else
      fail "$path is not writable by $APP_USER"
    fi
  elif check_command su; then
    if su -s /bin/sh "$APP_USER" -c "test -w '$path' && test -x '$path'"; then
      ok "$path is writable by $APP_USER"
    else
      fail "$path is not writable by $APP_USER"
    fi
  else
    fail "cannot verify $APP_USER write access: runuser/su not found"
  fi
}

if check_command python3; then
  ok "python3 found: $(command -v python3)"
else
  fail "python3 not found"
fi

if python3 -m venv -h >/dev/null 2>&1; then
  ok "python3 venv module available"
else
  warn "python3 venv module not available or not functional"
fi

if check_command pip3; then
  ok "pip3 found: $(command -v pip3)"
elif python3 -m pip --version >/dev/null 2>&1; then
  ok "python3 -m pip available"
else
  warn "pip not found"
fi

if [ -d /opt/totem/venv ]; then
  if [ -x /opt/totem/venv/bin/python ]; then
    ok "/opt/totem/venv/bin/python exists"
  else
    warn "/opt/totem/venv exists but bin/python is not executable yet"
  fi

  if [ -x /opt/totem/venv/bin/pip ]; then
    ok "/opt/totem/venv/bin/pip exists"
  else
    warn "/opt/totem/venv exists but bin/pip is not executable yet"
  fi
else
  warn "/opt/totem/venv does not exist yet"
fi

if check_command mpv; then
  ok "mpv found: $(command -v mpv)"
else
  fail "mpv not found"
fi

if id "$APP_USER" >/dev/null 2>&1; then
  ok "user exists: $APP_USER"
else
  fail "user missing: $APP_USER"
fi

if getent group "$APP_GROUP" >/dev/null; then
  ok "group exists: $APP_GROUP"
else
  fail "group missing: $APP_GROUP"
fi

check_path /data root root
check_path /data/config "$APP_USER" "$APP_GROUP"
check_path "$APP_MEDIA_DIR" "$APP_USER" "$APP_GROUP"
check_path /data/state/kiosky-player "$APP_USER" "$APP_GROUP"
check_path /data/spool/kiosky-player "$APP_USER" "$APP_GROUP"
check_path /data/logs/kiosky-player "$APP_USER" "$APP_GROUP"
check_path /tmp/kiosky "$APP_USER" "$APP_GROUP"

if id "$APP_USER" >/dev/null 2>&1; then
  check_user_writable_dir "$APP_MEDIA_DIR"
fi

if [ "$failures" -ne 0 ]; then
  echo
  echo "Prerequisite check failed: $failures error(s)." >&2
  exit 1
fi

echo
echo "Prerequisite check passed."
