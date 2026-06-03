#!/usr/bin/env bash
# C14.1.1 - Bootstrap script that runs ON the totem board.
# LEGACY C14 / BYPASS ONLY: not the C18 update path.
# For C18 release/update decisions, use docs/UPDATE_CONTRACT.md.
#
# Expects to be run from a directory that contains:
#   scripts/board/totem_updatectl.py
#   scripts/board/totem-kiosky-launcher.sh
#   scripts/board/kiosky_service_launcher.sh
#   scripts/board/systemd/kiosky-player.service.d/20-dadooh-launcher.conf
#   scripts/board/systemd/totem-update-agent.service
#   scripts/board/systemd/totem-update-agent.timer
#
# Idempotent. Safe to re-run.
#
# Does NOT: apt, pip, kernel/uboot/dtb/bsp, Wi-Fi, poweroff, reboot.
# Does NOT: write any secrets.

set -euo pipefail

STAMP() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
say() { printf '[c14_1_1_bootstrap %s] %s\n' "$(STAMP)" "$*"; }
warn() { printf '[c14_1_1_bootstrap %s] WARN %s\n' "$(STAMP)" "$*" >&2; }
die() { printf '[c14_1_1_bootstrap %s] FATAL %s\n' "$(STAMP)" "$*" >&2; exit 1; }

if [[ "${ALLOW_LEGACY_C14_UPDATE_BYPASS:-0}" != "1" ]]; then
  echo "FATAL: legacy C14 update bypass is disabled for C18. Set ALLOW_LEGACY_C14_UPDATE_BYPASS=1 only for an explicitly approved lab reproduction." >&2
  exit 44
fi

# Source dir (where the orchestrator unpacked us)
SRC_DIR="${C14_BOOTSTRAP_SRC_DIR:-$(pwd)}"
say "src_dir=${SRC_DIR}"

# Required source files
REQ_FILES=(
  "scripts/board/totem_updatectl.py"
  "scripts/board/totem-kiosky-launcher.sh"
  "scripts/board/kiosky_service_launcher.sh"
  "scripts/board/systemd/kiosky-player.service.d/20-dadooh-launcher.conf"
  "scripts/board/systemd/totem-update-agent.service"
  "scripts/board/systemd/totem-update-agent.timer"
)
for rel in "${REQ_FILES[@]}"; do
  [[ -f "${SRC_DIR}/${rel}" ]] || die "missing source file: ${rel}"
done

# Must run as root (we touch /opt/totem and /etc/systemd/system)
if [[ "$(id -u)" -ne 0 ]]; then
  die "must run as root"
fi

# Confirm we are on the lab board (cheap sanity)
if [[ ! -d /opt/totem ]]; then
  die "this device does not look like a totem appliance (/opt/totem missing)"
fi
if [[ ! -f /opt/totem/bin/kiosky_service_launcher.sh ]]; then
  die "expected /opt/totem/bin/kiosky_service_launcher.sh to exist on this image"
fi

# ============================================================================
# Capture pre-change state for evidence (saved under /data/state/c14-1-1/)
# ============================================================================
EVIDENCE_DIR="/data/state/c14-1-1"
mkdir -p "${EVIDENCE_DIR}"

say "capturing pre-change state"
systemctl cat kiosky-player.service > "${EVIDENCE_DIR}/pre-systemctl-cat-kiosky-player.txt" 2>&1 || true
systemctl status kiosky-player.service --no-pager --lines=0 \
  > "${EVIDENCE_DIR}/pre-systemctl-status-kiosky-player.txt" 2>&1 || true
ls -la /opt/totem/bin/ > "${EVIDENCE_DIR}/pre-opt-totem-bin.txt" 2>&1 || true

# ============================================================================
# Sanity: confirm the unit we'll override has the ExecStart shape we expect.
# If not, abort with KIOSKY_PLAYER_SERVICE_EXECSTART_UNCLEAR per Parte 7.
# ============================================================================
EXEC_LINE="$(systemctl cat kiosky-player.service 2>/dev/null | grep -E '^ExecStart=' || true)"
if [[ -z "$EXEC_LINE" ]]; then
  echo "KIOSKY_PLAYER_SERVICE_EXECSTART_UNCLEAR" >&2
  die "kiosky-player.service has no ExecStart= line that we can recognise"
fi
say "current ExecStart: ${EXEC_LINE}"

if ! grep -qE 'kiosky_service_launcher\.sh|totem-kiosky-launcher\.sh' \
        <<<"$EXEC_LINE"; then
  echo "KIOSKY_PLAYER_SERVICE_EXECSTART_UNCLEAR" >&2
  die "ExecStart does not point to an expected launcher; will not modify"
fi

# ============================================================================
# Create /data layout (idempotent)
# ============================================================================
say "creating /data layout"
install -d -m 0755 -o root -g root /data/apps
install -d -m 0755 -o root -g root /data/apps/kiosky-player
install -d -m 0755 -o root -g root /data/apps/kiosky-player/releases
install -d -m 0755 -o root -g root /data/updates
install -d -m 0755 -o root -g root /data/updates/incoming
install -d -m 0755 -o root -g root /data/logs

# /data/secrets is reserved for future device tokens. We do NOT create it now,
# per task ("não criar esse arquivo nesta rodada").
if [[ -d /data/secrets ]]; then
  say "/data/secrets exists (not created here)"
fi

# ============================================================================
# Install binaries to /opt/totem/bin
# ============================================================================
# We keep backups of the original kiosky_service_launcher.sh in case rollback
# is needed at the FS level (independent of /data/apps releases).
LAUNCHER_BACKUP_DIR="/opt/totem/.dadooh-c14-1-1-backup"
install -d -m 0755 "${LAUNCHER_BACKUP_DIR}"

if [[ ! -f "${LAUNCHER_BACKUP_DIR}/kiosky_service_launcher.sh.orig" ]]; then
  cp -a /opt/totem/bin/kiosky_service_launcher.sh \
        "${LAUNCHER_BACKUP_DIR}/kiosky_service_launcher.sh.orig"
  say "backed up original launcher to ${LAUNCHER_BACKUP_DIR}/kiosky_service_launcher.sh.orig"
fi

say "installing /opt/totem/bin/totem-updatectl"
install -m 0755 -o root -g root \
  "${SRC_DIR}/scripts/board/totem_updatectl.py" \
  /opt/totem/bin/totem-updatectl

say "installing /opt/totem/bin/totem-kiosky-launcher.sh"
install -m 0755 -o root -g root \
  "${SRC_DIR}/scripts/board/totem-kiosky-launcher.sh" \
  /opt/totem/bin/totem-kiosky-launcher.sh

say "installing updated /opt/totem/bin/kiosky_service_launcher.sh"
install -m 0755 -o root -g root \
  "${SRC_DIR}/scripts/board/kiosky_service_launcher.sh" \
  /opt/totem/bin/kiosky_service_launcher.sh

# ============================================================================
# Install systemd drop-in
# ============================================================================
DROPIN_DIR="/etc/systemd/system/kiosky-player.service.d"
DROPIN_FILE="${DROPIN_DIR}/20-dadooh-launcher.conf"
install -d -m 0755 "${DROPIN_DIR}"
install -m 0644 -o root -g root \
  "${SRC_DIR}/scripts/board/systemd/kiosky-player.service.d/20-dadooh-launcher.conf" \
  "${DROPIN_FILE}"
say "installed drop-in: ${DROPIN_FILE}"

# ============================================================================
# Install update-agent service + timer (disabled by default; do not enable)
# ============================================================================
install -m 0644 -o root -g root \
  "${SRC_DIR}/scripts/board/systemd/totem-update-agent.service" \
  /etc/systemd/system/totem-update-agent.service
install -m 0644 -o root -g root \
  "${SRC_DIR}/scripts/board/systemd/totem-update-agent.timer" \
  /etc/systemd/system/totem-update-agent.timer
say "installed totem-update-agent.{service,timer} (disabled)"

# ============================================================================
# Daemon-reload and restart kiosky-player
# ============================================================================
say "systemctl daemon-reload"
systemctl daemon-reload

say "restarting kiosky-player.service"
systemctl restart kiosky-player.service

# Wait briefly and capture post state
sleep 3

# ============================================================================
# Post-change evidence
# ============================================================================
systemctl cat kiosky-player.service > "${EVIDENCE_DIR}/post-systemctl-cat-kiosky-player.txt" 2>&1 || true
systemctl status kiosky-player.service --no-pager --lines=0 \
  > "${EVIDENCE_DIR}/post-systemctl-status-kiosky-player.txt" 2>&1 || true

systemctl is-active kiosky-player.service > "${EVIDENCE_DIR}/post-is-active.txt" 2>&1 || true
POST_ACTIVE="$(cat "${EVIDENCE_DIR}/post-is-active.txt" || echo unknown)"
say "post-restart is-active=${POST_ACTIVE}"

# ============================================================================
# Run updater self-test
# ============================================================================
say "running totem-updatectl self-test"
SELFTEST_OUT="${EVIDENCE_DIR}/selftest.json"
if /opt/totem/bin/totem-updatectl self-test > "${SELFTEST_OUT}" 2>&1; then
  say "self-test passed"
else
  warn "self-test FAILED — see ${SELFTEST_OUT}"
fi

# ============================================================================
# Final status summary (sanitised)
# ============================================================================
say "=== C14.1.1 bootstrap summary ==="
say "updatectl_installed=true"
say "launcher_installed=true"
say "service_dropin_installed=true"
say "service_active=${POST_ACTIVE}"
say "git_pull_used_on_device=false"
say "apt_update_executed=false"
say "apt_upgrade_executed=false"
say "pip_install_executed=false"
say "wifi_modified=false"
say "secrets_created=false"
say "poweroff_executed=false"
say "evidence_dir=${EVIDENCE_DIR}"
say "=== bootstrap complete ==="
