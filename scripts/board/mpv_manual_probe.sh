#!/usr/bin/env bash
set -u

umask 077

APP_USER="totem"
APP_GROUP="totem"
RUNTIME_DIR="/tmp/kiosky"
PROBE_DIR="$RUNTIME_DIR/mpv-probe"
MEDIA_FILE="$PROBE_DIR/testsrc-5s.mp4"
BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
RUN_NAME="mpv-manual-$TIMESTAMP"
OUT_DIR="$BASE_DIR/$RUN_NAME"
ARCHIVE="$BASE_DIR/$RUN_NAME.tar.gz"
SUMMARY="$OUT_DIR/summary.tsv"

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

  append_summary "$label" "$rc" "$title"
  return 0
}

skip_command() {
  local label="$1"
  local title="$2"
  local reason="$3"
  local stdout_file="$OUT_DIR/$label.stdout.txt"
  local stderr_file="$OUT_DIR/$label.stderr.txt"
  local meta_file="$OUT_DIR/$label.meta.txt"

  {
    echo "### $title"
    echo "### started: $(stamp)"
    echo "### skipped: $reason"
    echo "### exit_code: skipped"
    echo "### finished: $(stamp)"
    echo "stdout=$stdout_file"
    echo "stderr=$stderr_file"
  } >"$meta_file"
  : >"$stdout_file"
  printf '%s\n' "$reason" >"$stderr_file"

  append_summary "$label" "skipped" "$title: $reason"
}

{
  echo "mpv_manual_probe_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "run_name=$RUN_NAME"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "runtime_dir=$RUNTIME_DIR"
  echo "probe_dir=$PROBE_DIR"
  echo "media_file=$MEDIA_FILE"
  echo "hostname=$(hostname 2>/dev/null || true)"
  echo "created_at=$(stamp)"
} >"$OUT_DIR/manifest.txt"

printf 'label\texit_code\tnote\n' >"$SUMMARY"

if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "ERROR: user not found: $APP_USER" >&2
  append_summary "prereq-totem-user" "1" "missing user: $APP_USER"
  exit 1
fi

if ! getent group "$APP_GROUP" >/dev/null 2>&1; then
  echo "ERROR: group not found: $APP_GROUP" >&2
  append_summary "prereq-totem-group" "1" "missing group: $APP_GROUP"
  exit 1
fi

install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" "$RUNTIME_DIR"
install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" "$PROBE_DIR"
chmod 0750 "$RUNTIME_DIR" "$PROBE_DIR"
chown "$APP_USER:$APP_GROUP" "$RUNTIME_DIR" "$PROBE_DIR"

run_shell "pre-date" "date" "date"
run_shell "pre-uname-a" "uname -a" "uname -a"
run_shell "pre-etc-armbian-release" "cat /etc/armbian-release" "cat /etc/armbian-release"
run_shell "pre-systemctl-failed" "systemctl --failed" "systemctl --failed"
run_shell "pre-id-root" "id root" "id root"
run_shell "pre-id-totem" "id totem" "id totem"
run_shell "pre-groups-totem" "groups totem" "groups totem"
run_shell "pre-command-mpv" "command -v mpv" "command -v mpv"
run_shell "pre-mpv-version" "mpv --version" "mpv --version"
run_shell "pre-command-ffmpeg" "command -v ffmpeg" "command -v ffmpeg"
run_shell "pre-ffmpeg-version-head" "ffmpeg -version | head" "ffmpeg -version | head"
run_shell "pre-display-devices" "ls -l /dev/dri /dev/fb* 2>/dev/null || true" "ls -l /dev/dri /dev/fb* 2>/dev/null || true"
run_shell "pre-drm-status" "find /sys/class/drm -maxdepth 2 -type f -name status -print -exec cat {} \\; 2>/dev/null || true" "find /sys/class/drm -maxdepth 2 -type f -name status -print -exec cat {} \\; 2>/dev/null || true"
run_shell "pre-stat-tmp-kiosky" "stat /tmp/kiosky" "stat /tmp/kiosky"
run_shell "pre-stat-mpv-probe" "stat /tmp/kiosky/mpv-probe" "stat /tmp/kiosky/mpv-probe"

run_shell "media-generate" "generate local 5s ffmpeg test media" \
  "timeout 90s ffmpeg -nostdin -y -hide_banner -f lavfi -i testsrc=duration=5:size=640x360:rate=30 -c:v libx264 -preset ultrafast -crf 35 -pix_fmt yuv420p '$MEDIA_FILE'"

if [ -f "$MEDIA_FILE" ]; then
  chown "$APP_USER:$APP_GROUP" "$MEDIA_FILE"
  chmod 0640 "$MEDIA_FILE"
fi

run_shell "media-stat" "stat generated media" "stat '$MEDIA_FILE'"

run_shell "test-a-vo-null" "A. MPV parsing/decoding without video" \
  "timeout 20s mpv --no-config --vo=null --ao=null --frames=120 '$MEDIA_FILE'"

run_shell "test-b-vo-drm-root" "B. MPV DRM/KMS direct as root" \
  "timeout 20s mpv --no-config --vo=drm --profile=sw-fast --ao=null --fs '$MEDIA_FILE'"

run_shell "test-c-vo-gpu-drm-root" "C. MPV GPU with DRM context as root" \
  "timeout 20s mpv --no-config --vo=gpu --gpu-context=drm --hwdec=auto-safe --ao=null --fs '$MEDIA_FILE'"

if command -v runuser >/dev/null 2>&1; then
  run_shell "test-d-vo-drm-totem" "D. MPV DRM/KMS direct as totem" \
    "runuser -u '$APP_USER' -- env XDG_RUNTIME_DIR='$RUNTIME_DIR' timeout 20s mpv --no-config --vo=drm --profile=sw-fast --ao=null --fs '$MEDIA_FILE'"
  run_shell "test-e-vo-gpu-drm-totem" "E. MPV GPU with DRM context as totem" \
    "runuser -u '$APP_USER' -- env XDG_RUNTIME_DIR='$RUNTIME_DIR' timeout 20s mpv --no-config --vo=gpu --gpu-context=drm --hwdec=auto-safe --ao=null --fs '$MEDIA_FILE'"
else
  skip_command "test-d-vo-drm-totem" "D. MPV DRM/KMS direct as totem" "runuser not found"
  skip_command "test-e-vo-gpu-drm-totem" "E. MPV GPU with DRM context as totem" "runuser not found"
fi

run_shell "post-systemctl-failed" "systemctl --failed after MPV tests" "systemctl --failed"
run_shell "post-journalctl-kernel-display-filter" "journalctl kernel display/runtime filter after MPV tests" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'drm|gpu|mali|panfrost|display|hdmi|cedrus|v4l2|codec|video|fb0|framebuffer|mpv' || true"
run_shell "post-journalctl-kernel-critical-filter" "journalctl kernel critical filter after MPV tests" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true"
run_shell "post-ls-mpv-probe" "ls -lh /tmp/kiosky/mpv-probe" "ls -lh /tmp/kiosky/mpv-probe"

if command -v tar >/dev/null 2>&1; then
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME"
  tar_rc=$?
  if [ "$tar_rc" -eq 0 ]; then
    echo "MPV manual probe directory: $OUT_DIR"
    echo "Archive: $ARCHIVE"
  else
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    exit "$tar_rc"
  fi
else
  echo "ERROR: tar not found; probe directory kept at $OUT_DIR" >&2
  exit 127
fi
