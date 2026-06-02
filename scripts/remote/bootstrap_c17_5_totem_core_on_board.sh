#!/usr/bin/env bash
# C17.5 - Bootstrap totem-core wrappers/fallback/updatectl on the lab board.
#
# Runs on the builder and uses ssh/scp. The operator enters the SSH password
# interactively. The script does not store credentials and does not read or
# print appliance config, Wi-Fi details, NetworkManager profiles or secrets.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/builder/totem-os/orange_pi_totem}"
BOARD_HOST="${BOARD_HOST:-${1:-root@192.168.1.223}}"
REMOTE_DIR="/tmp/c17-5-totem-core-bootstrap"
RUN_PREVIEW_TEST="${RUN_PREVIEW_TEST:-0}"

CORE_FILES=(
  totem_setup_visual_wizard.py
  totem_wifi_nm_adapter.py
  totem_visual_splash.py
  totem_status_aggregate.py
  totem_status_render_preview.py
  totem_config_contract_validate.py
  totem_open_settings_session.sh
  totem_visual_tty_guard.sh
  totem_firstboot_gate.sh
  totem_status_renderer.sh
  totem_settings_trigger.py
  totem_open_settings_cleanup.sh
  totem_visual_setup_writer_handoff.py
  totem_config_writer_real.py
  totem_setup_minimal_server.py
  totem_setup_local_wizard.py
  kiosky_service_launcher.sh
)

say() { printf '[bootstrap_c17_5 %s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }
die() { printf '[bootstrap_c17_5 %s] FATAL %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >&2; exit 1; }

[[ -d "$REPO_ROOT/.git" ]] || die "REPO_ROOT is not a git repo: $REPO_ROOT"
[[ -f "$REPO_ROOT/scripts/board/totem_updatectl.py" ]] || die "missing totem_updatectl.py"
[[ -f "$REPO_ROOT/scripts/board/totem_update_policy.json" ]] || die "missing totem_update_policy.json"
[[ -f "$REPO_ROOT/scripts/board/totem_core_exec.py" ]] || die "missing totem_core_exec.py"
[[ -f "$REPO_ROOT/scripts/board/totem_core_exec.sh" ]] || die "missing totem_core_exec.sh"
for file in "${CORE_FILES[@]}"; do
  [[ -f "$REPO_ROOT/scripts/board/$file" ]] || die "missing scripts/board/$file"
done

WORK_DIR="$(mktemp -d -t c17-5-bootstrap-XXXXXX)"
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

mkdir -p "$WORK_DIR/scripts/board"
install -m 0755 "$REPO_ROOT/scripts/board/totem_updatectl.py" "$WORK_DIR/scripts/board/totem_updatectl.py"
install -m 0644 "$REPO_ROOT/scripts/board/totem_update_policy.json" "$WORK_DIR/scripts/board/totem_update_policy.json"
install -m 0755 "$REPO_ROOT/scripts/board/totem_core_exec.py" "$WORK_DIR/scripts/board/totem_core_exec.py"
install -m 0755 "$REPO_ROOT/scripts/board/totem_core_exec.sh" "$WORK_DIR/scripts/board/totem_core_exec.sh"
for file in "${CORE_FILES[@]}"; do
  install -m 0755 "$REPO_ROOT/scripts/board/$file" "$WORK_DIR/scripts/board/$file"
done

cat > "$WORK_DIR/remote-bootstrap.sh" <<'REMOTE'
#!/usr/bin/env bash
set -euo pipefail

STAMP() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
say() { printf '[c17_5_board_bootstrap %s] %s\n' "$(STAMP)" "$*"; }
die() { printf '[c17_5_board_bootstrap %s] FATAL %s\n' "$(STAMP)" "$*" >&2; exit 1; }

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_PREVIEW_TEST="${RUN_PREVIEW_TEST:-0}"
CORE_FILES=(
  totem_setup_visual_wizard.py
  totem_wifi_nm_adapter.py
  totem_visual_splash.py
  totem_status_aggregate.py
  totem_status_render_preview.py
  totem_config_contract_validate.py
  totem_open_settings_session.sh
  totem_visual_tty_guard.sh
  totem_firstboot_gate.sh
  totem_status_renderer.sh
  totem_settings_trigger.py
  totem_open_settings_cleanup.sh
  totem_visual_setup_writer_handoff.py
  totem_config_writer_real.py
  totem_setup_minimal_server.py
  totem_setup_local_wizard.py
  kiosky_service_launcher.sh
)

[[ "$(id -u)" -eq 0 ]] || die "must run as root"
[[ -d /opt/totem/bin ]] || die "not a totem appliance: /opt/totem/bin missing"

EVIDENCE_DIR="/data/state/c17-5-totem-core-bootstrap"
install -d -m 0700 -o root -g root "$EVIDENCE_DIR"

service_state() { systemctl is-active "$1" 2>/dev/null || true; }

settings_state="$(service_state totem-open-settings.service)"
if [[ -e /run/totem/settings-session.lock || "$settings_state" == "active" || "$settings_state" == "activating" ]]; then
  die "settings session active; refusing bootstrap"
fi

player_active="$(service_state kiosky-player.service)"
network_active="$(service_state NetworkManager.service)"
ssh_active="$(service_state ssh.service)"
if [[ -z "$ssh_active" || "$ssh_active" == "unknown" ]]; then
  ssh_active="$(service_state sshd.service)"
fi

cat > "$EVIDENCE_DIR/pre-state.env" <<EOF
player_active=${player_active}
networkmanager_active=${network_active}
ssh_active=${ssh_active}
settings_session_lock_present=false
config_real_present=$([[ -f /data/config/config.json ]] && echo true || echo false)
seed_present=$([[ -f /data/state/totem-settings/private-values.seed.json ]] && echo true || echo false)
EOF
chmod 0600 "$EVIDENCE_DIR/pre-state.env"

install -d -m 0755 -o root -g root /opt/totem/core-fallback /opt/totem/core-fallback/bin
install -d -m 0755 -o root -g root /opt/totem/core-fallback/original-pre-c17-5
install -d -m 0755 -o root -g root /data/core /data/core/totem /data/core/totem/releases
install -d -m 0755 -o root -g root /data/updates /data/updates/incoming /data/updates/incoming/totem-core /data/logs
if [[ ! -e /data/updates/policy.json ]]; then
  install -m 0644 -o root -g root "$SRC_DIR/scripts/board/totem_update_policy.json" /data/updates/policy.json
  policy_created=true
else
  policy_created=false
fi

is_wrapper() {
  local path="$1"
  grep -q "TOTEM_CORE_EXEC_WRAPPER" "$path" 2>/dev/null
}

for file in "${CORE_FILES[@]}"; do
  src="/opt/totem/bin/$file"
  fallback="/opt/totem/core-fallback/bin/$file"
  original="/opt/totem/core-fallback/original-pre-c17-5/$file"
  if [[ ! -f "$original" && -f "$src" ]] && ! is_wrapper "$src"; then
    install -m 0755 -o root -g root "$src" "$original"
  fi
  install -m 0755 -o root -g root "$SRC_DIR/scripts/board/$file" "$fallback"
done

for file in "${CORE_FILES[@]}"; do
  case "$file" in
    *.py)
      install -m 0755 -o root -g root "$SRC_DIR/scripts/board/totem_core_exec.py" "/opt/totem/bin/$file"
      ;;
    *.sh)
      install -m 0755 -o root -g root "$SRC_DIR/scripts/board/totem_core_exec.sh" "/opt/totem/bin/$file"
      ;;
  esac
done

install -m 0755 -o root -g root "$SRC_DIR/scripts/board/totem_updatectl.py" /opt/totem/bin/totem-updatectl

TOTEM_CORE_DISABLE_DATA=1 /usr/bin/python3 /opt/totem/bin/totem_setup_visual_wizard.py --self-test >/dev/null
TOTEM_CORE_DISABLE_DATA=1 /usr/bin/python3 /opt/totem/bin/totem_wifi_nm_adapter.py --self-test >/dev/null
TOTEM_CORE_DISABLE_DATA=1 /usr/bin/python3 /opt/totem/bin/totem_visual_splash.py --self-test >/dev/null
TOTEM_CORE_DISABLE_DATA=1 /usr/bin/python3 /opt/totem/bin/totem_config_contract_validate.py --self-test >/dev/null
TOTEM_CORE_DISABLE_DATA=1 /opt/totem/bin/totem_open_settings_session.sh --help >/dev/null

/opt/totem/bin/totem-updatectl self-test --component totem-core > "$EVIDENCE_DIR/totem-core-self-test.json"

preview_result="not_run"
if [[ "$RUN_PREVIEW_TEST" == "1" ]]; then
  if /opt/totem/bin/totem_open_settings_session.sh \
      --mode preview --expect preview --preview-sec 4 --timeout-sec 30 \
      --out-dir /tmp/c17-5-preview-session \
      --wizard-out-dir /tmp/c17-5-preview-wizard >/dev/null 2>&1; then
    preview_result="passed"
  else
    preview_result="failed"
  fi
fi

cat > "$EVIDENCE_DIR/bootstrap-status.env" <<EOF
board_bootstrap_applied=true
totem_core_layout_created=true
totem_core_wrappers_created=true
totem_core_fallback_available=true
totem_updatectl_multi_component=true
totem_update_policy_created=${policy_created}
wizard_fallback_to_opt_tested=true
f10_preview_test=${preview_result}
writer_called=false
real_config_written=false
wifi_real_changed=false
networkmanager_touched=false
poweroff_executed=false
EOF
chmod 0600 "$EVIDENCE_DIR/bootstrap-status.env"

say "board_bootstrap_applied=true"
say "totem_core_layout_created=true"
say "totem_core_wrappers_created=true"
say "totem_core_fallback_available=true"
say "totem_updatectl_multi_component=true"
say "totem_update_policy_created=${policy_created}"
say "wizard_fallback_to_opt_tested=true"
say "f10_preview_test=${preview_result}"
REMOTE
chmod 0755 "$WORK_DIR/remote-bootstrap.sh"

BUNDLE="$WORK_DIR/c17-5-totem-core-bootstrap.tar.gz"
tar -C "$WORK_DIR" -czf "$BUNDLE" scripts remote-bootstrap.sh

say "copying bootstrap bundle to board"
scp -o StrictHostKeyChecking=accept-new "$BUNDLE" "$BOARD_HOST:/tmp/c17-5-totem-core-bootstrap.tar.gz"

say "running remote bootstrap"
ssh -t -o StrictHostKeyChecking=accept-new "$BOARD_HOST" "
  set -euo pipefail
  rm -rf '$REMOTE_DIR'
  mkdir -p '$REMOTE_DIR'
  tar -xzf /tmp/c17-5-totem-core-bootstrap.tar.gz -C '$REMOTE_DIR'
  RUN_PREVIEW_TEST='$RUN_PREVIEW_TEST' '$REMOTE_DIR/remote-bootstrap.sh'
"

say "bootstrap complete"
