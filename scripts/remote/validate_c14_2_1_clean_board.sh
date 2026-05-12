#!/usr/bin/env bash
# C14.2.1 - Validate a clean board freshly flashed with the shipping
# homologation image.
#
# Runs from the BUILDER host. One SSH session.  Operator types password once.
#
# Validates that the C14.1.1 pull updater is embedded and active, and that
# the totem-update-agent.timer is enabled+active.  Also exercises one
# manual apply-github-latest to prove end-to-end.
#
# DOES NOT touch Wi-Fi, NetworkManager, apt, pip, kernel, U-Boot, DTB,
# BSP, or the seed.  DOES NOT print SSH password.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/builder/totem-os/orange_pi_totem}"
BOARD_HOST="${BOARD_HOST:-${1:-}}"
GH_REPO="${GH_REPO:-dadoohai/kiosky-player}"
OUTPUT_LOG="${OUTPUT_LOG:-${REPO_ROOT}/.cache/c14-2-1-clean-board-validate.out}"

if [[ -z "$BOARD_HOST" ]]; then
  echo "Usage: BOARD_HOST=root@<lab-ip> $(basename "$0")" >&2
  echo "   or: $(basename "$0") root@<lab-ip>" >&2
  exit 2
fi

say() { printf '[validate_c14_2_1 %s] %s\n' \
        "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }

mkdir -p "$(dirname "$OUTPUT_LOG")"

{
  echo "=== validate_c14_2_1 begin $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
  ssh -t \
      -o StrictHostKeyChecking=accept-new \
      -o ServerAliveInterval=15 \
      -o ServerAliveCountMax=3 \
      "$BOARD_HOST" "
    set -e
    echo '--- image identity ---'
    cat /etc/dadooh/c12-lab-firstboot-mode 2>/dev/null || true
    echo
    cat /etc/dadooh/c13-homologation-private-seed 2>/dev/null || true
    echo

    echo '--- file presence (C14.1.1 embedded) ---'
    test -x /opt/totem/bin/totem-updatectl                                   && echo updatectl=present || echo updatectl=MISSING
    test -x /opt/totem/bin/totem-kiosky-launcher.sh                          && echo launcher=present  || echo launcher=MISSING
    test -f /etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf \
       && echo dropin=present || echo dropin=MISSING
    test -f /etc/systemd/system/totem-update-agent.service                   && echo agent_svc=present  || echo agent_svc=MISSING
    test -f /etc/systemd/system/totem-update-agent.timer                     && echo agent_timer=present || echo agent_timer=MISSING

    echo '--- seed sanity (no content read) ---'
    stat -c '%a %U:%G %n' /data/state/totem-settings/private-values.seed.json 2>/dev/null || echo seed=MISSING
    test -f /data/state/totem-settings/homologation-seed.enabled && echo seed_marker=present || echo seed_marker=MISSING

    echo '--- /data layout ---'
    for d in /data/apps /data/apps/kiosky-player /data/apps/kiosky-player/releases /data/updates /data/updates/incoming /data/logs; do
      test -d \$d && echo \"\$d=present\" || echo \"\$d=MISSING\"
    done

    echo '--- systemd ---'
    systemctl is-active   kiosky-player.service          || true
    systemctl is-enabled  kiosky-player.service          || true
    systemctl is-enabled  totem-update-agent.timer       || true
    systemctl is-active   totem-update-agent.timer       || true
    systemctl cat         kiosky-player.service | grep -E '^ExecStart=' | head -2

    echo '--- updater status + self-test ---'
    /opt/totem/bin/totem-updatectl self-test
    /opt/totem/bin/totem-updatectl status

    echo '--- apt/pip/git pull invocation history (none expected from timer) ---'
    journalctl -u totem-update-agent.service --no-pager -n 100 2>/dev/null \
      | grep -E 'apt-get|pip install|git pull' || echo \"no apt/pip/git pull lines found in agent journal\"

    echo '--- manual apply-github-latest (smoke) ---'
    /opt/totem/bin/totem-updatectl apply-github-latest --repo '${GH_REPO}'
    APPLY_RC=\$?
    echo \"apply_exit=\$APPLY_RC\"

    echo '--- post-apply status ---'
    /opt/totem/bin/totem-updatectl status
    readlink -f /data/apps/kiosky-player/current || true
    systemctl is-active kiosky-player.service || true

    echo '--- update log tail (sanitised) ---'
    tail -n 50 /data/logs/totem-update.log 2>/dev/null || true

    exit \$APPLY_RC
  "
  echo "=== validate_c14_2_1 end $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
} 2>&1 | tee "$OUTPUT_LOG"

say "captured: $OUTPUT_LOG"
