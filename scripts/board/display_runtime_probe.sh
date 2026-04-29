#!/usr/bin/env bash
set -u

umask 077

BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
RUN_NAME="display-runtime-$TIMESTAMP"
OUT_DIR="$BASE_DIR/$RUN_NAME"
ARCHIVE="$BASE_DIR/$RUN_NAME.tar.gz"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

run_cmd() {
  local title="$1"
  local outfile="$2"
  shift 2
  local rc=0

  {
    echo "### $title"
    echo "### started: $(stamp)"
    echo "### command: $*"
    echo
    "$@"
    rc=$?
    echo
    echo "### exit_code: $rc"
    echo "### finished: $(stamp)"
  } >"$OUT_DIR/$outfile" 2>&1
}

run_shell() {
  local title="$1"
  local outfile="$2"
  local command="$3"
  local rc=0

  {
    echo "### $title"
    echo "### started: $(stamp)"
    echo "### command: $command"
    echo
    sh -c "$command"
    rc=$?
    echo
    echo "### exit_code: $rc"
    echo "### finished: $(stamp)"
  } >"$OUT_DIR/$outfile" 2>&1
}

{
  echo "display_runtime_probe_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "hostname=$(hostname 2>/dev/null || true)"
  echo "created_at=$(stamp)"
} >"$OUT_DIR/manifest.txt"

run_cmd "date" "date.txt" date
run_cmd "uname -a" "uname-a.txt" uname -a
run_cmd "/etc/armbian-release" "etc-armbian-release.txt" cat /etc/armbian-release
run_cmd "systemctl --failed" "systemctl-failed.txt" systemctl --failed
run_cmd "systemctl get-default" "systemctl-get-default.txt" systemctl get-default

run_shell "command -v python3" "command-python3.txt" "command -v python3"
run_cmd "python3 --version" "python3-version.txt" python3 --version
run_shell "command -v pip3" "command-pip3.txt" "command -v pip3 || true"
run_shell "python3 -m pip --version" "python3-m-pip-version.txt" "python3 -m pip --version || true"
run_shell "python3 -m venv -h" "python3-m-venv-help.txt" "python3 -m venv -h || true"

run_shell "command -v mpv" "command-mpv.txt" "command -v mpv || true"
run_shell "command -v Xorg" "command-xorg.txt" "command -v Xorg || true"
run_shell "command -v xinit" "command-xinit.txt" "command -v xinit || true"
run_shell "command -v weston" "command-weston.txt" "command -v weston || true"
run_shell "command -v cage" "command-cage.txt" "command -v cage || true"
run_shell "command -v openbox" "command-openbox.txt" "command -v openbox || true"
run_shell "command -v chromium" "command-chromium.txt" "command -v chromium || true"
run_shell "command -v ffmpeg" "command-ffmpeg.txt" "command -v ffmpeg || true"

run_shell "display devices" "display-devices.txt" \
  "ls -l /dev/dri /dev/fb* 2>/dev/null || true"
run_shell "DRM connector status" "drm-status.txt" \
  "find /sys/class/drm -maxdepth 2 -type f -name status -print -exec cat {} \\; 2>/dev/null || true"
run_shell "DRM symlinks" "drm-symlinks.txt" \
  "find /sys/class/drm -maxdepth 2 -type l -print -exec readlink -f {} \\; 2>/dev/null || true"

run_shell "id totem" "totem-id.txt" "id totem || true"
run_shell "getent passwd totem" "totem-passwd.txt" "getent passwd totem || true"
run_shell "getent group totem" "totem-group.txt" "getent group totem || true"
run_shell "groups totem" "totem-groups.txt" "groups totem || true"

run_shell "runtime path stat" "runtime-path-stat.txt" '
for path in \
  /opt/totem \
  /opt/totem/kiosky-player \
  /opt/totem/venv \
  /data/config \
  /data/media/kiosky-player \
  /data/state/kiosky-player \
  /data/spool/kiosky-player \
  /data/logs/kiosky-player \
  /tmp/kiosky
do
  echo "## $path"
  stat "$path" 2>&1 || true
  echo
done
'

run_shell "dpkg display/runtime packages" "dpkg-display-runtime-packages.txt" \
  "if command -v dpkg >/dev/null 2>&1; then dpkg -l | grep -Ei 'mpv|ffmpeg|python3-venv|python3-pip|python3-requests|xserver|xorg|xinit|openbox|wayland|weston|cage|mesa|libdrm|panfrost|chromium|kms|drm' || true; else echo 'dpkg not found'; fi"

run_shell "apt-cache policy display/runtime packages" "apt-cache-policy-display-runtime-packages.txt" '
if command -v apt-cache >/dev/null 2>&1; then
  for pkg in \
    mpv \
    ffmpeg \
    python3-venv \
    python3-pip \
    python3-requests \
    xserver-xorg \
    xinit \
    openbox \
    cage \
    weston \
    chromium \
    mesa-utils \
    libdrm-tests
  do
    echo "## $pkg"
    apt-cache policy "$pkg" 2>&1 || true
    echo
  done
else
  echo "apt-cache not found"
fi
'

run_shell "journalctl kernel display/runtime filter" "journalctl-kernel-display-runtime-filter.txt" \
  "if command -v journalctl >/dev/null 2>&1; then journalctl -k -b --no-pager --output=short-iso | grep -Ei 'drm|gpu|mali|panfrost|display|hdmi|cedrus|v4l2|codec|video|fb0|framebuffer' || true; else echo 'journalctl not found'; fi"
run_shell "journalctl kernel critical filter" "journalctl-kernel-critical-filter.txt" \
  "if command -v journalctl >/dev/null 2>&1; then journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true; else echo 'journalctl not found'; fi"

if command -v tar >/dev/null 2>&1; then
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME"
  tar_rc=$?
  if [ "$tar_rc" -eq 0 ]; then
    echo "Diagnostic directory: $OUT_DIR"
    echo "Archive: $ARCHIVE"
  else
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    exit "$tar_rc"
  fi
else
  echo "ERROR: tar not found; diagnostic directory kept at $OUT_DIR" >&2
  exit 127
fi
