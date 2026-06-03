#!/usr/bin/env bash
# C14.1.1 — Rollback to previous release on the lab board (Part 10).
# LEGACY C14 / BYPASS ONLY: not the C18 update path.
# For C18 release/update decisions, use docs/UPDATE_CONTRACT.md.
#
# Runs on the BUILDER host. Opens one ssh session and runs:
#   /opt/totem/bin/totem-updatectl rollback
#   /opt/totem/bin/totem-updatectl status
#
# Operator types SSH password once.

set -euo pipefail

case " ${*:-} " in
  *" -h "*|*" --help "*) ;;
  *)
    if [[ "${ALLOW_LEGACY_C14_UPDATE_BYPASS:-0}" != "1" ]]; then
      echo "FATAL: legacy C14 update bypass is disabled for C18. Set ALLOW_LEGACY_C14_UPDATE_BYPASS=1 only for an explicitly approved lab reproduction." >&2
      exit 44
    fi
    ;;
esac

REPO_ROOT="${REPO_ROOT:-/home/builder/totem-os/orange_pi_totem}"
BOARD_HOST="${BOARD_HOST:-${1:-}}"
OUTPUT_LOG="${OUTPUT_LOG:-${REPO_ROOT}/.cache/c14-1-1-rollback.out}"

if [[ -z "$BOARD_HOST" ]]; then
  echo "Usage: BOARD_HOST=root@<lab-ip> $(basename "$0")" >&2
  echo "   or: $(basename "$0") root@<lab-ip>" >&2
  exit 2
fi

say() { printf '[rollback_c14_1_1 %s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }
mkdir -p "$(dirname "$OUTPUT_LOG")"

say "BOARD_HOST=${BOARD_HOST}"

{
  echo "=== rollback_c14_1_1 begin $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
  ssh -t \
      -o StrictHostKeyChecking=accept-new \
      -o ServerAliveInterval=15 \
      -o ServerAliveCountMax=3 \
      "$BOARD_HOST" "
    set -e
    echo '--- pre-rollback status ---'
    /opt/totem/bin/totem-updatectl status || true
    echo '--- rollback ---'
    /opt/totem/bin/totem-updatectl rollback
    echo '--- post-rollback status ---'
    /opt/totem/bin/totem-updatectl status || true
    echo '--- systemctl is-active kiosky-player.service ---'
    systemctl is-active kiosky-player.service || true
  "
  echo "=== rollback_c14_1_1 end $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
} 2>&1 | tee "$OUTPUT_LOG"

say "captured: $OUTPUT_LOG"
