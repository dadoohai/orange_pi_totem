#!/usr/bin/env bash
set -eu

usage() {
  cat >&2 <<'USAGE'
Usage:
  scripts/remote/push_and_run.sh <user@host> <scripts/board/script.sh>
  scripts/remote/push_and_run.sh <host> <user> <scripts/board/script.sh>

Examples:
  ./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/collect_diag.sh
  ./scripts/remote/push_and_run.sh orangepizero3 root scripts/board/network_snapshot.sh
USAGE
}

if [ "$#" -eq 2 ]; then
  TARGET="$1"
  SCRIPT="$2"
elif [ "$#" -eq 3 ]; then
  TARGET="$2@$1"
  SCRIPT="$3"
else
  usage
  exit 64
fi

case "$TARGET" in
  *@*) ;;
  *)
    echo "ERROR: target must include user, for example root@orangepizero3." >&2
    exit 64
    ;;
esac

if [ ! -f "$SCRIPT" ]; then
  echo "ERROR: script not found: $SCRIPT" >&2
  exit 66
fi

case "$SCRIPT" in
  scripts/board/*|*/scripts/board/*) ;;
  *)
    echo "ERROR: expected a board script under scripts/board/." >&2
    exit 64
    ;;
esac

SCRIPT_NAME="$(basename "$SCRIPT")"
case "$SCRIPT_NAME" in
  *[!A-Za-z0-9._-]*|'')
    echo "ERROR: unsafe script filename: $SCRIPT_NAME" >&2
    exit 64
    ;;
esac

command -v scp >/dev/null 2>&1 || {
  echo "ERROR: scp not found." >&2
  exit 127
}

command -v ssh >/dev/null 2>&1 || {
  echo "ERROR: ssh not found." >&2
  exit 127
}

REMOTE_DIR="/tmp/totem-board-scripts"
REMOTE_SCRIPT="$REMOTE_DIR/$SCRIPT_NAME"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT")" && pwd)"

ssh "$TARGET" "mkdir -p '$REMOTE_DIR'"

if [ "$SCRIPT_NAME" != "collect_diag.sh" ] && [ -f "$SCRIPT_DIR/collect_diag.sh" ]; then
  scp "$SCRIPT_DIR/collect_diag.sh" "$TARGET:$REMOTE_DIR/collect_diag.sh"
fi

scp "$SCRIPT" "$TARGET:$REMOTE_SCRIPT"

ssh -t "$TARGET" \
  "chmod 700 '$REMOTE_DIR'/*.sh && if [ \"\$(id -u)\" -eq 0 ]; then '$REMOTE_SCRIPT'; else sudo '$REMOTE_SCRIPT'; fi"
