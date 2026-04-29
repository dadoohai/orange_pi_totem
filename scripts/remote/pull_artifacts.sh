#!/usr/bin/env bash
set -eu

REMOTE_DIR='/root/totem-diag'
DEFAULT_ARTIFACT_PATTERN='*.tar.gz'

usage() {
  cat >&2 <<'USAGE'
Usage:
  scripts/remote/pull_artifacts.sh <user@host> <local-destination-dir> [artifact-pattern]

Examples:
  ./scripts/remote/pull_artifacts.sh root@orangepizero3 docs/evidence/candidate-a/runs/2026-04-28/
  ./scripts/remote/pull_artifacts.sh root@orangepizero3 docs/evidence/candidate-a/runs/20260429-012638-data-layout/ "totem-diag-20260429-012629-0300.tar.gz"
  ./scripts/remote/pull_artifacts.sh root@orangepizero3 docs/evidence/candidate-a/runs/20260429-012638-data-layout/ "totem-diag-20260429-0126*.tar.gz"
USAGE
}

if [ "$#" -ne 2 ] && [ "$#" -ne 3 ]; then
  usage
  exit 64
fi

TARGET="$1"
DEST_DIR="$2"
ARTIFACT_PATTERN="${3:-$DEFAULT_ARTIFACT_PATTERN}"

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

case "$ARTIFACT_PATTERN" in
  ''|*/*)
    echo "ERROR: artifact pattern must be a filename pattern, not a path." >&2
    exit 64
    ;;
esac

case "$ARTIFACT_PATTERN" in
  *[!abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._*?-]*)
    echo "ERROR: artifact pattern contains unsupported characters." >&2
    exit 64
    ;;
esac

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
  ssh "$TARGET" "find '$REMOTE_DIR' -maxdepth 1 -type f -name '$ARTIFACT_PATTERN' -print 2>/dev/null | sort"
)"

if [ -z "$REMOTE_LIST" ]; then
  echo "ERROR: no artifacts found on $TARGET matching $REMOTE_DIR/$ARTIFACT_PATTERN" >&2
  exit 1
fi

echo "Remote artifacts to copy:"
printf '%s\n' "$REMOTE_LIST"

printf '%s\n' "$REMOTE_LIST" | while IFS= read -r remote_file; do
  [ -n "$remote_file" ] || continue
  scp "$TARGET:$remote_file" "$DEST_DIR/"
done

echo "Artifacts copied to: $DEST_DIR"
