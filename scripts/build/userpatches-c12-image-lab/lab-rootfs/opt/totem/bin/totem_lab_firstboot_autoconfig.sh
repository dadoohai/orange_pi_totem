#!/usr/bin/env bash
set -euo pipefail

CONF="${CONF:-/root/.not_logged_in_yet}"
MARKER="${MARKER:-/etc/dadooh/image-lab-firstboot-autoconfig.present}"
STATUS_DIR="${STATUS_DIR:-/run/dadooh-lab-firstboot}"
STATUS_FILE="$STATUS_DIR/status.json"
WIFI_CONN_NAME="${WIFI_CONN_NAME:-dadooh-lab-wifi}"

write_status() {
  local state="$1"
  local reason="${2:-ok}"
  local network_attempted="${3:-false}"
  local marker_removed="${4:-false}"
  python3 - "$STATUS_FILE" "$state" "$reason" "$network_attempted" "$marker_removed" <<'PY'
import json
import os
import pathlib
import sys
import time

target = pathlib.Path(sys.argv[1])
payload = {
    "schema_version": "dadooh-c12-lab-firstboot-autoconfig.v1",
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "state": sys.argv[2],
    "reason": sys.argv[3],
    "network_apply_attempted": sys.argv[4] == "true",
    "firstboot_marker_removed": sys.argv[5] == "true",
    "secrets_published": False,
    "config_real_embedded": False,
    "writer_called": False,
}
target.parent.mkdir(parents=True, exist_ok=True)
os.chmod(target.parent, 0o700)
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
PY
}

fail() {
  write_status "failed" "$1" "false" "false"
  exit 1
}

validate_name() {
  printf '%s' "$1" | grep -Eq '^[A-Za-z][A-Za-z0-9]*$'
}

main() {
  mkdir -p "$STATUS_DIR"
  chmod 700 "$STATUS_DIR"

  if [ ! -f "$MARKER" ]; then
    write_status "skipped" "lab_marker_missing"
    exit 0
  fi
  if [ ! -s "$CONF" ]; then
    write_status "skipped" "firstboot_conf_missing"
    exit 0
  fi
  bash -n "$CONF" || fail "firstboot_conf_syntax_invalid"
  if grep -Eq 'REPLACE_WITH_PRIVATE_LAB_|RootPassword|UserPassword|MySSID|MyWiFiKEY' "$CONF"; then
    fail "firstboot_conf_placeholder_present"
  fi

  # shellcheck disable=SC1090
  source "$CONF"

  : "${PRESET_NET_CHANGE_DEFAULTS:?}"
  : "${PRESET_NET_ETHERNET_ENABLED:?}"
  : "${PRESET_NET_WIFI_ENABLED:?}"
  : "${PRESET_USER_NAME:?}"
  : "${PRESET_ROOT_PASSWORD:?}"
  : "${PRESET_USER_PASSWORD:?}"
  : "${PRESET_DEFAULT_REALNAME:?}"

  if ! validate_name "$PRESET_USER_NAME"; then
    fail "preset_user_name_invalid"
  fi

  printf 'root:%s\n' "$PRESET_ROOT_PASSWORD" | chpasswd >/dev/null 2>&1

  local user
  user="$(printf '%s' "$PRESET_USER_NAME" | tr '[:upper:]' '[:lower:]' | tr -d -c '[:alnum:]')"
  if ! id "$user" >/dev/null 2>&1; then
    useradd -m -s "/bin/${PRESET_USER_SHELL:-bash}" -c "$PRESET_DEFAULT_REALNAME" "$user"
  fi
  printf '%s:%s\n' "$user" "$PRESET_USER_PASSWORD" | chpasswd >/dev/null 2>&1
  for group in sudo netdev audio video dialout plugdev input systemd-journal users; do
    getent group "$group" >/dev/null 2>&1 && usermod -aG "$group" "$user" >/dev/null 2>&1 || true
  done

  local network_attempted="false"
  if [ "${PRESET_NET_CHANGE_DEFAULTS:-0}" = "1" ] &&
    [ "${PRESET_NET_WIFI_ENABLED:-0}" = "1" ] &&
    [ -n "${PRESET_NET_WIFI_SSID:-}" ] &&
    [ -n "${PRESET_NET_WIFI_KEY:-}" ] &&
    command -v nmcli >/dev/null 2>&1; then
    network_attempted="true"
    nmcli radio wifi on >/dev/null 2>&1 || true
    nmcli connection delete "$WIFI_CONN_NAME" >/dev/null 2>&1 || true
    nmcli connection add type wifi ifname "*" con-name "$WIFI_CONN_NAME" ssid "$PRESET_NET_WIFI_SSID" >/dev/null 2>&1 || true
    nmcli connection modify "$WIFI_CONN_NAME" \
      connection.autoconnect yes \
      wifi-sec.key-mgmt wpa-psk \
      wifi-sec.psk "$PRESET_NET_WIFI_KEY" >/dev/null 2>&1 || true
    nmcli connection up "$WIFI_CONN_NAME" >/dev/null 2>&1 || true
  fi

  if [ -n "${PRESET_TIMEZONE:-}" ] && command -v timedatectl >/dev/null 2>&1; then
    timedatectl set-timezone "$PRESET_TIMEZONE" >/dev/null 2>&1 || true
  fi

  rm -f "$CONF"
  write_status "complete" "ok" "$network_attempted" "true"
}

main "$@"
