#!/usr/bin/env bash
# C14.1.1 Part 10 - Test rollback path end-to-end on the lab board.
#
# Pre-requisite: at least one app release is already installed on the device
# (e.g. via run_c14_1_1_github_releases_pull_deploy_mvp.sh --apply-after).
#
# What this does in ONE ssh session:
#   1. apply-github-latest  -> moves current to v2, sets previous=v1
#   2. status               -> confirm current=v2, previous=v1
#   3. rollback             -> swap back so current=v1
#   4. status               -> confirm current=v1
#   5. verify service active
#
# Operator types SSH password once.
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/builder/totem-os/orange_pi_totem}"
BOARD_HOST="${BOARD_HOST:-${1:-}}"
GH_REPO="${GH_REPO:-dadoohai/kiosky-player}"
OUTPUT_LOG="${OUTPUT_LOG:-${REPO_ROOT}/.cache/c14-1-1-rollback-test.out}"

if [[ -z "$BOARD_HOST" ]]; then
  echo "Usage: BOARD_HOST=root@<lab-ip> $(basename "$0")" >&2
  echo "   or: $(basename "$0") root@<lab-ip>" >&2
  exit 2
fi

say() { printf '[test_rollback %s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }
mkdir -p "$(dirname "$OUTPUT_LOG")"

{
  echo "=== test_rollback_c14_1_1 begin $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
  ssh -t \
      -o StrictHostKeyChecking=accept-new \
      -o ServerAliveInterval=15 \
      -o ServerAliveCountMax=3 \
      "$BOARD_HOST" "
    set -e
    echo '--- step 1: apply latest (will set previous = current) ---'
    /opt/totem/bin/totem-updatectl apply-github-latest --repo '${GH_REPO}'
    echo '--- step 2: status after apply ---'
    /opt/totem/bin/totem-updatectl status
    echo '--- ls /data/apps/kiosky-player ---'
    ls -la /data/apps/kiosky-player/
    echo '--- step 3: rollback ---'
    /opt/totem/bin/totem-updatectl rollback
    echo '--- step 4: status after rollback ---'
    /opt/totem/bin/totem-updatectl status
    echo '--- ls /data/apps/kiosky-player ---'
    ls -la /data/apps/kiosky-player/
    echo '--- step 5: is-active ---'
    systemctl is-active kiosky-player.service || true
    echo '--- log tail (sanitised) ---'
    tail -n 40 /data/logs/totem-update.log || true
  "
  echo "=== test_rollback_c14_1_1 end $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
} 2>&1 | tee "$OUTPUT_LOG"

say "captured: $OUTPUT_LOG"
