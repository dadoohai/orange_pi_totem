#!/usr/bin/env bash
set -eu

REMOTE_APP_DIR="/opt/totem/kiosky-player"

usage() {
  cat >&2 <<'USAGE'
Usage:
  scripts/remote/deploy_kiosky_player.sh <root@host> <local-kiosky-player-dir>

Example:
  ./scripts/remote/deploy_kiosky_player.sh root@<orange-pi> /path/to/kiosky-player

This copies application code only. It does not install dependencies, copy private
config, enable systemd, or start the app.
USAGE
}

if [ "$#" -ne 2 ]; then
  usage
  exit 64
fi

TARGET="$1"
SOURCE_DIR="$2"

case "$TARGET" in
  *@*) ;;
  *)
    echo "ERROR: target must include user, for example root@orangepizero3." >&2
    exit 64
    ;;
esac

case "$TARGET" in
  *[!A-Za-z0-9._@:-]*)
    echo "ERROR: target contains unsupported characters." >&2
    exit 64
    ;;
esac

if [ ! -d "$SOURCE_DIR" ]; then
  echo "ERROR: local kiosky-player directory not found: $SOURCE_DIR" >&2
  exit 66
fi

SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd)"

if [ ! -f "$SOURCE_DIR/kiosk.py" ]; then
  echo "ERROR: kiosk.py not found in source directory: $SOURCE_DIR" >&2
  exit 66
fi

for config_file in "$SOURCE_DIR"/config*.json; do
  [ -e "$config_file" ] || continue
  config_name="$(basename "$config_file")"
  case "$config_name" in
    config.example.json|config.appliance.example.json) ;;
    *)
      echo "ERROR: refusing to deploy possible private config file: $config_name" >&2
      echo "Move private config outside the checkout and create /data/config/config.json separately." >&2
      exit 65
      ;;
  esac
done

command -v ssh >/dev/null 2>&1 || {
  echo "ERROR: ssh not found." >&2
  exit 127
}

echo "Deploy source: $SOURCE_DIR"
echo "Deploy target: $TARGET:$REMOTE_APP_DIR"
echo "Private config is intentionally excluded. Create /data/config/config.json separately."

ssh "$TARGET" "install -d -m 0755 -o root -g root /opt/totem '$REMOTE_APP_DIR'"

if command -v rsync >/dev/null 2>&1; then
  rsync -av \
    --no-owner \
    --no-group \
    --exclude '.git/' \
    --exclude '__pycache__/' \
    --exclude '*/__pycache__/' \
    --exclude '.pytest_cache/' \
    --exclude '*/.pytest_cache/' \
    --exclude '.venv/' \
    --exclude '*/.venv/' \
    --exclude 'venv/' \
    --exclude 'media_cache/' \
    --exclude 'config.json' \
    --exclude 'config.local.json' \
    --exclude 'config.*.local.json' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude '*.pyc' \
    --exclude '*.secret*' \
    "$SOURCE_DIR/" "$TARGET:$REMOTE_APP_DIR/"
else
  command -v tar >/dev/null 2>&1 || {
    echo "ERROR: rsync not found and tar fallback is unavailable." >&2
    exit 127
  }

  tar -czf - \
    -C "$SOURCE_DIR" \
    --exclude './.git' \
    --exclude './__pycache__' \
    --exclude './*/__pycache__' \
    --exclude './.pytest_cache' \
    --exclude './*/.pytest_cache' \
    --exclude './.venv' \
    --exclude './*/.venv' \
    --exclude './venv' \
    --exclude './media_cache' \
    --exclude './config.json' \
    --exclude './config.local.json' \
    --exclude './config.*.local.json' \
    --exclude './.env' \
    --exclude './.env.*' \
    --exclude './*.pyc' \
    --exclude './*.secret*' \
    . | ssh "$TARGET" "tar -xzf - --no-same-owner --no-same-permissions -C '$REMOTE_APP_DIR'"
fi

ssh "$TARGET" "chown -R root:root '$REMOTE_APP_DIR' && find '$REMOTE_APP_DIR' -type d -exec chmod 0755 {} + && find '$REMOTE_APP_DIR' -type f -exec chmod u=rw,go=r {} +"

echo
echo "Deploy completed. Review files on the board before creating config or enabling any service."
