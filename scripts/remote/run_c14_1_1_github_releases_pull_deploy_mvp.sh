#!/usr/bin/env bash
# C14.1.1 — Orchestrator: ship board files + run bootstrap on the lab board.
#
# Run this script on the BUILDER host (not on the board).
# It opens a single SSH session and:
#   1. tars the required files
#   2. pipes them over stdin to the board
#   3. runs bootstrap_c14_1_1_on_board.sh on the board
#   4. captures sanitised summary output
#
# The operator will be prompted for the SSH password once (interactive).
#
# Usage:
#   bash scripts/remote/run_c14_1_1_github_releases_pull_deploy_mvp.sh
#
# Env overrides:
#   BOARD_HOST=root@<lab-ip>           ssh target (REQUIRED — no default)
#   REPO_ROOT=/home/builder/totem-os/orange_pi_totem
#   REMOTE_TMP=/tmp/dadooh-c14-1-1-bootstrap
#   OUTPUT_LOG=${REPO_ROOT}/.cache/c14-1-1-bootstrap.out
#
# Does NOT save the password. Does NOT log the password. Does NOT print secrets.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/builder/totem-os/orange_pi_totem}"
BOARD_HOST="${BOARD_HOST:-${1:-}}"
REMOTE_TMP="${REMOTE_TMP:-/tmp/dadooh-c14-1-1-bootstrap}"
OUTPUT_LOG="${OUTPUT_LOG:-${REPO_ROOT}/.cache/c14-1-1-bootstrap.out}"
GH_REPO="${GH_REPO:-dadoohai/kiosky-player}"

if [[ -z "$BOARD_HOST" ]]; then
  echo "Usage: BOARD_HOST=root@<lab-ip> $(basename "$0") [--apply-after]" >&2
  echo "   or: $(basename "$0") root@<lab-ip> [--apply-after]" >&2
  exit 2
fi
# If $1 was used as BOARD_HOST, drop it from $@ so the option parser below
# sees only flags.
if [[ "${1:-}" == "$BOARD_HOST" ]]; then shift; fi

APPLY_AFTER=0
for arg in "$@"; do
  case "$arg" in
    --apply-after) APPLY_AFTER=1 ;;
    --no-apply)    APPLY_AFTER=0 ;;
    --gh-repo=*)   GH_REPO="${arg#*=}" ;;
    -h|--help)
      cat <<EOF
Usage: $(basename "$0") [--apply-after] [--gh-repo=owner/repo]

  --apply-after    After bootstrap, run totem-updatectl apply-github-latest
                   in the same SSH session.
  --no-apply       Bootstrap only (default).
  --gh-repo        GitHub repo to pull from (default: $GH_REPO).

Env overrides: BOARD_HOST, REPO_ROOT, REMOTE_TMP, OUTPUT_LOG.
EOF
      exit 0 ;;
    *) echo "FATAL: unknown arg: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '[run_c14_1_1 %s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }
die() { printf '[run_c14_1_1] FATAL %s\n' "$*" >&2; exit 1; }

cd "$REPO_ROOT"
mkdir -p "$(dirname "$OUTPUT_LOG")"

# Files to ship to the board (paths relative to REPO_ROOT)
FILES=(
  scripts/board/totem_updatectl.py
  scripts/board/totem-kiosky-launcher.sh
  scripts/board/kiosky_service_launcher.sh
  scripts/board/systemd/kiosky-player.service.d/20-dadooh-launcher.conf
  scripts/board/systemd/totem-update-agent.service
  scripts/board/systemd/totem-update-agent.timer
  scripts/remote/bootstrap_c14_1_1_on_board.sh
)

for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || die "missing file in repo: $f"
done

say "BOARD_HOST=${BOARD_HOST}"
say "REMOTE_TMP=${REMOTE_TMP}"
say "bundling: ${FILES[*]}"

# Build the bootstrap pipeline.  One ssh -t session.  Operator types password once.
# We use a remote sh -c that:
#   1. cleans REMOTE_TMP (so re-runs are deterministic)
#   2. untars stdin into REMOTE_TMP
#   3. runs the on-board bootstrap
# Output is teed to OUTPUT_LOG on the builder side.
{
  echo "=== run_c14_1_1 begin $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
  tar -czf - "${FILES[@]}" | \
    ssh -t \
        -o StrictHostKeyChecking=accept-new \
        -o ServerAliveInterval=15 \
        -o ServerAliveCountMax=3 \
        "$BOARD_HOST" "
      set -e
      umask 022
      rm -rf '${REMOTE_TMP}'
      mkdir -p '${REMOTE_TMP}'
      tar -xzf - -C '${REMOTE_TMP}'
      chmod +x '${REMOTE_TMP}/scripts/remote/bootstrap_c14_1_1_on_board.sh'
      cd '${REMOTE_TMP}'
      bash './scripts/remote/bootstrap_c14_1_1_on_board.sh'
      if [ '${APPLY_AFTER}' = '1' ]; then
        echo '=== applying latest release ==='
        /opt/totem/bin/totem-updatectl check-github-latest --repo '${GH_REPO}' || true
        echo '--- apply-github-latest ---'
        /opt/totem/bin/totem-updatectl apply-github-latest --repo '${GH_REPO}'
        echo '--- status ---'
        /opt/totem/bin/totem-updatectl status || true
        echo '--- is-active ---'
        systemctl is-active kiosky-player.service || true
        echo '--- ls /data/apps/kiosky-player ---'
        ls -la /data/apps/kiosky-player/ || true
        echo '--- log tail (sanitised) ---'
        tail -n 40 /data/logs/totem-update.log || true
      fi
    "
  echo "=== run_c14_1_1 end $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
} 2>&1 | tee "$OUTPUT_LOG"

say "captured output: $OUTPUT_LOG"
