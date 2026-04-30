#!/usr/bin/env bash
set -u

umask 077

APP_USER="totem"
APP_GROUP="totem"
RUNTIME_DIR="/tmp/kiosky"
BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
RUN_NAME="media-isolated-$TIMESTAMP"
OUT_DIR="$BASE_DIR/$RUN_NAME"
ARCHIVE="$BASE_DIR/$RUN_NAME.tar.gz"
SUMMARY="$OUT_DIR/summary.tsv"
MPV_NULL_LOG="$RUNTIME_DIR/media-isolated-$TIMESTAMP-vo-null.log"
MPV_DRM_LOG="$RUNTIME_DIR/media-isolated-$TIMESTAMP-drm.log"
TIMEOUT_SEC="${MEDIA_ISOLATED_TIMEOUT_SEC:-60}"
HWDEC="${MEDIA_ISOLATED_HWDEC:-auto-safe}"
MEDIA_ROOT="/data/media/kiosky-player"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /absolute/local/media-file" >&2
  exit 2
fi

MEDIA_PATH="$1"

case "$MEDIA_PATH" in
  *://*)
    echo "ERROR: URLs are not accepted; pass a local media path." >&2
    exit 2
    ;;
  /*)
    ;;
  *)
    echo "ERROR: media path must be absolute." >&2
    exit 2
    ;;
esac

if [ ! -f "$MEDIA_PATH" ]; then
  echo "ERROR: media path is not a regular file." >&2
  exit 2
fi

MEDIA_REALPATH="$(readlink -f -- "$MEDIA_PATH" 2>/dev/null || true)"
if [ -z "$MEDIA_REALPATH" ]; then
  echo "ERROR: failed to resolve media path." >&2
  exit 2
fi

case "$MEDIA_REALPATH" in
  "$MEDIA_ROOT"/*)
    MEDIA_PATH="$MEDIA_REALPATH"
    ;;
  *)
    echo "ERROR: media path must be under $MEDIA_ROOT." >&2
    exit 2
    ;;
esac

case "$TIMEOUT_SEC" in
  ''|*[!0-9]*)
    echo "ERROR: MEDIA_ISOLATED_TIMEOUT_SEC must be a positive integer." >&2
    exit 2
    ;;
  0)
    echo "ERROR: MEDIA_ISOLATED_TIMEOUT_SEC must be greater than zero." >&2
    exit 2
    ;;
esac

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

safe_media_alias() {
  printf '%s' "$MEDIA_PATH" | sha1sum | awk '{print "<media-path:" substr($1, 1, 10) ">"}'
}

run_shell() {
  local label="$1"
  local title="$2"
  local command="$3"
  local safe_command="$4"
  local stdout_file="$OUT_DIR/$label.stdout.txt"
  local stderr_file="$OUT_DIR/$label.stderr.txt"
  local meta_file="$OUT_DIR/$label.meta.txt"
  local rc=0

  {
    echo "### $title"
    echo "### started: $(stamp)"
    echo "### command: $safe_command"
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

copy_mpv_log() {
  local label="$1"
  local source="$2"
  local dest_name="$3"
  local dest="$OUT_DIR/$dest_name"
  local size=0

  if [ -f "$source" ]; then
    cp "$source" "$dest"
    chmod 0600 "$dest"
    size=$(wc -c <"$source" 2>/dev/null || printf '0')
    append_summary "$label" "0" "$dest_name copied from runtime log; bytes=$size"
  else
    append_summary "$label" "missing" "$dest_name runtime log not present"
  fi
}

MEDIA_ALIAS="$(safe_media_alias)"
MEDIA_SIZE="$(wc -c <"$MEDIA_PATH" 2>/dev/null || printf 'unknown')"
MEDIA_BASENAME="$(basename "$MEDIA_PATH")"
MEDIA_EXT="${MEDIA_BASENAME##*.}"
if [ "$MEDIA_EXT" = "$MEDIA_BASENAME" ]; then
  MEDIA_EXT="none"
fi

export MEDIA_ISOLATED_TARGET="$MEDIA_PATH"
export MEDIA_ISOLATED_MPV_NULL_LOG="$MPV_NULL_LOG"
export MEDIA_ISOLATED_MPV_DRM_LOG="$MPV_DRM_LOG"
export MEDIA_ISOLATED_HWDEC="$HWDEC"
export MEDIA_ISOLATED_TIMEOUT_SEC_VALUE="$TIMEOUT_SEC"

{
  echo "media_isolated_probe_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "run_name=$RUN_NAME"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "runtime_dir=$RUNTIME_DIR"
  echo "media_alias=$MEDIA_ALIAS"
  echo "media_size_bytes=$MEDIA_SIZE"
  echo "media_extension=$MEDIA_EXT"
  echo "media_root=$MEDIA_ROOT"
  echo "timeout_sec=$TIMEOUT_SEC"
  echo "hwdec=$HWDEC"
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

run_shell "pre-date" "date" \
  "date" \
  "date"
run_shell "pre-uname-a" "uname -a" \
  "uname -a" \
  "uname -a"
run_shell "pre-systemctl-failed" "systemctl --failed" \
  "systemctl --failed" \
  "systemctl --failed"
run_shell "pre-id-totem" "id totem" \
  "id totem" \
  "id totem"
run_shell "pre-command-mpv" "command -v mpv" \
  "command -v mpv" \
  "command -v mpv"
run_shell "media-stat-sanitized" "stat isolated media without path disclosure" \
  "stat -c 'size=%s mode=%a uid=%u gid=%g type=%F' \"\$MEDIA_ISOLATED_TARGET\"" \
  "stat -c 'size=%s mode=%a uid=%u gid=%g type=%F' '$MEDIA_ALIAS'"

if command -v ffprobe >/dev/null 2>&1; then
  run_shell "media-ffprobe" "ffprobe selected stream metadata" \
    "ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate,duration -of default=noprint_wrappers=1:nokey=0 \"\$MEDIA_ISOLATED_TARGET\"" \
    "ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate,duration -of default=noprint_wrappers=1:nokey=0 '$MEDIA_ALIAS'"
else
  append_summary "media-ffprobe" "skipped" "ffprobe not found"
fi

if command -v runuser >/dev/null 2>&1; then
  run_shell "mpv-isolated-vo-null-totem" "MPV isolated decode without video as totem" \
    "runuser -u '$APP_USER' -- env XDG_RUNTIME_DIR='$RUNTIME_DIR' timeout \"\${MEDIA_ISOLATED_TIMEOUT_SEC_VALUE}s\" mpv --no-config --no-terminal --no-osc --osd-level=0 --vo=null --ao=null --log-file=\"\$MEDIA_ISOLATED_MPV_NULL_LOG\" --msg-level=all=v \"\$MEDIA_ISOLATED_TARGET\"" \
    "runuser -u '$APP_USER' -- env XDG_RUNTIME_DIR='$RUNTIME_DIR' timeout '${TIMEOUT_SEC}s' mpv --no-config --no-terminal --no-osc --osd-level=0 --vo=null --ao=null --log-file='$MPV_NULL_LOG' --msg-level=all=v '$MEDIA_ALIAS'"
  copy_mpv_log "mpv-vo-null-log-copy" "$MPV_NULL_LOG" "mpv-vo-null.log"
  run_shell "mpv-isolated-drm-totem" "MPV isolated DRM/KMS playback as totem" \
    "runuser -u '$APP_USER' -- env XDG_RUNTIME_DIR='$RUNTIME_DIR' timeout \"\${MEDIA_ISOLATED_TIMEOUT_SEC_VALUE}s\" mpv --no-config --fs --force-window=yes --no-terminal --no-osc --osd-level=0 --vo=gpu --gpu-context=drm --ao=null --hwdec=\"\$MEDIA_ISOLATED_HWDEC\" --log-file=\"\$MEDIA_ISOLATED_MPV_DRM_LOG\" --msg-level=all=v \"\$MEDIA_ISOLATED_TARGET\"" \
    "runuser -u '$APP_USER' -- env XDG_RUNTIME_DIR='$RUNTIME_DIR' timeout '${TIMEOUT_SEC}s' mpv --no-config --fs --force-window=yes --no-terminal --no-osc --osd-level=0 --vo=gpu --gpu-context=drm --ao=null --hwdec='$HWDEC' --log-file='$MPV_DRM_LOG' --msg-level=all=v '$MEDIA_ALIAS'"
  copy_mpv_log "mpv-drm-log-copy" "$MPV_DRM_LOG" "mpv-drm.log"
else
  append_summary "mpv-isolated-vo-null-totem" "skipped" "runuser not found"
  append_summary "mpv-isolated-drm-totem" "skipped" "runuser not found"
fi

run_shell "post-systemctl-failed" "systemctl --failed after isolated media probe" \
  "systemctl --failed" \
  "systemctl --failed"
run_shell "post-journalctl-kernel-critical-filter" "journalctl kernel critical filter after isolated media probe" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true"

if command -v tar >/dev/null 2>&1; then
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME"
  tar_rc=$?
  if [ "$tar_rc" -eq 0 ]; then
    echo "Media isolated probe directory: $OUT_DIR"
    echo "Archive: $ARCHIVE"
  else
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    exit "$tar_rc"
  fi
else
  echo "ERROR: tar not found; probe directory kept at $OUT_DIR" >&2
  exit 127
fi
