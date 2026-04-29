#!/usr/bin/env bash
set -u

umask 077

APP_USER="totem"
APP_GROUP="totem"
APP_DIR="/opt/totem/kiosky-player"
APP_ENTRY="$APP_DIR/kiosk.py"
CONFIG_PATH="/data/config/config.json"
RUNTIME_DIR="/tmp/kiosky"
STATUS_FILE="/tmp/kiosky-status.json"
BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
RUN_NAME="kiosky-manual-$TIMESTAMP"
OUT_DIR="$BASE_DIR/$RUN_NAME"
ARCHIVE="$BASE_DIR/$RUN_NAME.tar.gz"
SUMMARY="$OUT_DIR/summary.tsv"
MARKER="/tmp/kiosky-manual-$TIMESTAMP.marker"
RUN_SHELL_LAST_RC=0

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

append_summary() {
  local label="$1"
  local rc="$2"
  local note="$3"

  printf '%s\t%s\t%s\n' "$label" "$rc" "$note" >>"$SUMMARY"
}

run_shell() {
  local label="$1"
  local title="$2"
  local command="$3"
  local stdout_file="$OUT_DIR/$label.stdout.txt"
  local stderr_file="$OUT_DIR/$label.stderr.txt"
  local meta_file="$OUT_DIR/$label.meta.txt"
  local rc=0

  {
    echo "### $title"
    echo "### started: $(stamp)"
    echo "### command: $command"
  } >"$meta_file"

  sh -c "$command" >"$stdout_file" 2>"$stderr_file"
  rc=$?

  {
    echo "### exit_code: $rc"
    echo "### finished: $(stamp)"
    echo "stdout=$stdout_file"
    echo "stderr=$stderr_file"
  } >>"$meta_file"

  RUN_SHELL_LAST_RC="$rc"
  append_summary "$label" "$rc" "$title"
  return 0
}

check_config_placeholders() {
  local label="pre-config-placeholder-check"
  local title="check config for blocking placeholders without printing secrets"
  local stdout_file="$OUT_DIR/$label.stdout.txt"
  local stderr_file="$OUT_DIR/$label.stderr.txt"
  local meta_file="$OUT_DIR/$label.meta.txt"
  local rc=0

  {
    echo "### $title"
    echo "### started: $(stamp)"
    echo "### command: python3 placeholder check for $CONFIG_PATH"
  } >"$meta_file"

  python3 - "$CONFIG_PATH" >"$stdout_file" 2>"$stderr_file" <<'PY'
import json
import sys

config_path = sys.argv[1]
with open(config_path, "r", encoding="utf-8") as fh:
    cfg = json.load(fh)

errors = []


def contains_placeholder(value, placeholder):
    return isinstance(value, str) and placeholder in value


def check_value(label, value, placeholders):
    for placeholder in placeholders:
        if contains_placeholder(value, placeholder):
            errors.append(f"{label} contains blocked placeholder: {placeholder}")


check_value("api_url", cfg.get("api_url"), ["api.example.invalid"])
check_value(
    "api_key",
    cfg.get("api_key"),
    ["replace-with-api-key", "replace-with-real-api-key"],
)
check_value(
    "environment_id",
    cfg.get("environment_id"),
    ["replace-with-environment-id", "replace-with-real-environment-id"],
)

telemetry_enabled = cfg.get("telemetry_enabled")
if isinstance(telemetry_enabled, str):
    telemetry_enabled = telemetry_enabled.strip().lower() in {"1", "true", "yes", "on"}
if telemetry_enabled is True:
    check_value("telemetry_url", cfg.get("telemetry_url"), ["telemetry.example.invalid"])

if errors:
    for error in errors:
        print(f"BLOCK: {error}")
    sys.exit(1)

print("OK: no blocking placeholders detected")
PY
  rc=$?

  {
    echo "### exit_code: $rc"
    echo "### finished: $(stamp)"
    echo "stdout=$stdout_file"
    echo "stderr=$stderr_file"
  } >>"$meta_file"

  RUN_SHELL_LAST_RC="$rc"
  append_summary "$label" "$rc" "$title"
  return 0
}

copy_status_file() {
  local phase="$1"
  local dest="$OUT_DIR/$phase-kiosky-status.json"

  if [ -f "$STATUS_FILE" ]; then
    cp "$STATUS_FILE" "$dest"
    chmod 0600 "$dest"
    append_summary "$phase-status-copy" "0" "$STATUS_FILE copied to artifact without printing content"
  else
    append_summary "$phase-status-copy" "missing" "$STATUS_FILE not present"
  fi
}

finish_archive() {
  if command -v tar >/dev/null 2>&1; then
    tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME"
    tar_rc=$?
    if [ "$tar_rc" -eq 0 ]; then
      echo "Kiosky manual probe directory: $OUT_DIR"
      echo "Archive: $ARCHIVE"
      return 0
    fi
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    return "$tar_rc"
  fi

  echo "ERROR: tar not found; probe directory kept at $OUT_DIR" >&2
  return 127
}

{
  echo "kiosky_manual_probe_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "run_name=$RUN_NAME"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "app_dir=$APP_DIR"
  echo "app_entry=$APP_ENTRY"
  echo "config_path=$CONFIG_PATH"
  echo "runtime_dir=$RUNTIME_DIR"
  echo "status_file=$STATUS_FILE"
  echo "marker=$MARKER"
  echo "hostname=$(hostname 2>/dev/null || true)"
  echo "created_at=$(stamp)"
} >"$OUT_DIR/manifest.txt"

printf 'label\texit_code\tnote\n' >"$SUMMARY"

if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "ERROR: user not found: $APP_USER" >&2
  append_summary "prereq-user" "1" "missing user: $APP_USER"
  finish_archive
  exit 1
fi

if ! getent group "$APP_GROUP" >/dev/null 2>&1; then
  echo "ERROR: group not found: $APP_GROUP" >&2
  append_summary "prereq-group" "1" "missing group: $APP_GROUP"
  finish_archive
  exit 1
fi

install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" "$RUNTIME_DIR"
chmod 0750 "$RUNTIME_DIR"
chown "$APP_USER:$APP_GROUP" "$RUNTIME_DIR"

run_shell "pre-date" "date before app run" "date"
run_shell "pre-uname-a" "uname -a before app run" "uname -a"
run_shell "pre-systemctl-failed" "systemctl --failed before app run" "systemctl --failed"
run_shell "pre-id-totem" "id totem before app run" "id totem"
run_shell "pre-command-mpv" "command -v mpv before app run" "command -v mpv"
run_shell "pre-python-requests" "python3 requests version before app run" "python3 -c 'import requests; print(requests.__version__)'"
run_shell "pre-stat-app-dir" "stat /opt/totem/kiosky-player before app run" "stat '$APP_DIR'"
run_shell "pre-stat-config" "stat /data/config/config.json before app run without printing content" "stat '$CONFIG_PATH'"
run_shell "pre-data-media-files" "media files before app run" "find /data/media/kiosky-player -maxdepth 2 -type f -printf '%s %p\n' 2>/dev/null | sort || true"
run_shell "pre-data-state-files" "state files before app run" "find /data/state/kiosky-player -maxdepth 2 -type f -printf '%s %p\n' 2>/dev/null | sort || true"
run_shell "pre-ls-runtime-dir" "ls -lh /tmp/kiosky before app run" "ls -lh '$RUNTIME_DIR'"
run_shell "pre-processes-totem" "totem kiosk/mpv processes before app run" "pgrep -a -u '$APP_USER' -f 'kiosk.py|mpv' || true"
run_shell "pre-processes-all" "all kiosk/mpv processes before app run" "pgrep -a -f 'kiosk.py|mpv' || true"
run_shell "pre-journalctl-kernel-display-filter" "journalctl kernel DRM/display filter before app run" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'drm|gpu|mali|panfrost|display|hdmi|cedrus|v4l2|codec|video|fb0|framebuffer|mpv' || true"
run_shell "pre-journalctl-kernel-critical-filter" "journalctl kernel critical filter before app run" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true"
copy_status_file "pre"

if [ ! -f "$CONFIG_PATH" ]; then
  echo "ERROR: required config not found: $CONFIG_PATH" >&2
  append_summary "prereq-config" "1" "missing config: $CONFIG_PATH"
  finish_archive
  exit 1
fi

if [ ! -f "$APP_ENTRY" ]; then
  echo "ERROR: application entrypoint not found: $APP_ENTRY" >&2
  append_summary "prereq-app-entry" "1" "missing app entrypoint: $APP_ENTRY"
  finish_archive
  exit 1
fi

run_shell "pre-config-json-valid" "validate config JSON without printing content" "python3 -m json.tool '$CONFIG_PATH' >/dev/null"
if [ "$RUN_SHELL_LAST_RC" -ne 0 ]; then
  echo "ERROR: config is not valid JSON: $CONFIG_PATH" >&2
  append_summary "prereq-config-json" "1" "invalid JSON; app was not started"
  finish_archive
  exit 1
fi

check_config_placeholders
if [ "$RUN_SHELL_LAST_RC" -ne 0 ]; then
  echo "ERROR: config contains blocking placeholder(s); app was not started." >&2
  append_summary "prereq-config-placeholders" "1" "blocking placeholder detected; app was not started"
  finish_archive
  exit 1
fi

touch "$MARKER"
chmod 0600 "$MARKER"
append_summary "marker-created" "0" "$MARKER"

if command -v runuser >/dev/null 2>&1; then
  run_shell "app-run" "manual kiosky-player run as totem with 300s timeout" \
    "cd '$APP_DIR' && runuser -u '$APP_USER' -- env PYTHONDONTWRITEBYTECODE=1 XDG_RUNTIME_DIR='$RUNTIME_DIR' timeout 300s python3 '$APP_ENTRY' --config '$CONFIG_PATH'"
else
  echo "ERROR: runuser not found; cannot run app as $APP_USER" >&2
  append_summary "app-run" "127" "runuser not found; app was not started"
fi

run_shell "post-date" "date after app run" "date"
run_shell "post-uname-a" "uname -a after app run" "uname -a"
run_shell "post-systemctl-failed" "systemctl --failed after app run" "systemctl --failed"
run_shell "post-id-totem" "id totem after app run" "id totem"
run_shell "post-command-mpv" "command -v mpv after app run" "command -v mpv"
run_shell "post-python-requests" "python3 requests version after app run" "python3 -c 'import requests; print(requests.__version__)'"
run_shell "post-stat-app-dir" "stat /opt/totem/kiosky-player after app run" "stat '$APP_DIR'"
run_shell "post-stat-config" "stat /data/config/config.json after app run without printing content" "stat '$CONFIG_PATH'"
run_shell "post-data-media-files" "media files after app run" "find /data/media/kiosky-player -maxdepth 2 -type f -printf '%s %p\n' 2>/dev/null | sort || true"
run_shell "post-data-state-files" "state files after app run" "find /data/state/kiosky-player -maxdepth 2 -type f -printf '%s %p\n' 2>/dev/null | sort || true"
run_shell "post-ls-runtime-dir" "ls -lh /tmp/kiosky after app run" "ls -lh '$RUNTIME_DIR'"
run_shell "post-processes-totem" "totem kiosk/mpv processes after app run" "pgrep -a -u '$APP_USER' -f 'kiosk.py|mpv' || true"
run_shell "post-processes-all" "all kiosk/mpv processes after app run" "pgrep -a -f 'kiosk.py|mpv' || true"
run_shell "post-opt-newer-marker" "files written under /opt/totem/kiosky-player after marker" \
  "find '$APP_DIR' -newer '$MARKER' -printf '%TY-%Tm-%TdT%TH:%TM:%TS %u %g %m %p\n' 2>/dev/null | sort || true"
run_shell "post-journalctl-kernel-display-filter" "journalctl kernel DRM/display filter after app run" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'drm|gpu|mali|panfrost|display|hdmi|cedrus|v4l2|codec|video|fb0|framebuffer|mpv' || true"
run_shell "post-journalctl-kernel-critical-filter" "journalctl kernel critical filter after app run" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true"
copy_status_file "post"

finish_archive
