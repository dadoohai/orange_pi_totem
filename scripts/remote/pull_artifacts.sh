#!/usr/bin/env bash
set -eu

REMOTE_GLOB='/root/totem-diag/*.tar.gz'

usage() {
  cat >&2 <<'USAGE'
Usage:
  scripts/remote/pull_artifacts.sh <user@host> <local-destination-dir>

Example:
  ./scripts/remote/pull_artifacts.sh root@orangepizero3 docs/evidence/candidate-a/runs/2026-04-28/
USAGE
}

if [ "$#" -ne 2 ]; then
  usage
  exit 64
fi

TARGET="$1"
DEST_DIR="$2"

case "$TARGET" in
  *@*) ;;
  *)
    echo "ERROR: target must include user, for example root@orangepizero3." >&2
    exit 64
    ;;
esac

if [ -z "$DEST_DIR" ]; then
  echo "ERROR: local destination directory is required." >&2
  exit 64
fi

command -v ssh >/dev/null 2>&1 || {
  echo "ERROR: ssh not found." >&2
  exit 127
}

command -v scp >/dev/null 2>&1 || {
  echo "ERROR: scp not found." >&2
  exit 127
}

mkdir -p "$DEST_DIR"

REMOTE_LIST="$(
  ssh "$TARGET" \
    "find /root/totem-diag -maxdepth 1 -type f -name '*.tar.gz' -print 2>/dev/null | sort"
)"

if [ -z "$REMOTE_LIST" ]; then
  echo "ERROR: no artifacts found on $TARGET matching $REMOTE_GLOB" >&2
  exit 1
fi

echo "Remote artifacts:"
printf '%s\n' "$REMOTE_LIST"

scp "$TARGET:$REMOTE_GLOB" "$DEST_DIR/"

echo "Artifacts copied to: $DEST_DIR"
