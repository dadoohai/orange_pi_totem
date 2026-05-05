#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
TIMESTAMP="${C10_9_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c10-9-second-board-clean-install}"
LOCAL_OUT_DIR="${C10_9_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c10-9-second-board-clean-install}"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/dadooh-c10-9-second-board-clean-install}"
REMOTE_REPO="$REMOTE_ROOT/repo-$TIMESTAMP"
REMOTE_OUT_DIR="$REMOTE_ROOT/out-$TIMESTAMP"
REMOTE_APP_ARCHIVE="$REMOTE_ROOT/kiosky-player-$TIMESTAMP.tar.gz"
REMOTE_APP_PIN="$REMOTE_ROOT/kiosky-player-pin-$TIMESTAMP.json"
KIOSKY_PLAYER_DIR="${KIOSKY_PLAYER_DIR:-/home/builder/kiosky-player}"
INSTALL_RUNTIME=0
F10_WAIT_SEC="${F10_WAIT_SEC:-300}"
REBOOT_WAIT_SEC="${REBOOT_WAIT_SEC:-300}"

INSTALL_CONFIRM_PHRASE="CONFIRMO INSTALAR APPLIANCE C10.9 NA SEGUNDA PLACA"
REBOOT_CONFIRM_PHRASE="CONFIRMO REBOOT C10.9 SEGUNDA PLACA"
F10_CONFIRM_PHRASE="CONFIRMO F10 CHECK C10.9 SEGUNDA PLACA"
PROVISION_CONFIRM_PHRASE="CONFIRMO PROVISIONAR CONFIG REAL C10.9 NA SEGUNDA PLACA"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_9_second_board_clean_install.sh <root@host> [mode] [options]

Modes:
  --prepare-only
  --inspect-base
  --install-dry-run
  --install-apply
  --verify
  --idempotence-check
  --config-missing-check
  --f10-check
  --reboot-check
  --provision-real-config

Options:
  --install-runtime
      With --install-apply only, allow the board installer to run explicit
      apt-get install --no-install-recommends for the manifest runtime packages.
      It never runs upgrade/full-upgrade/dist-upgrade/armbian-upgrade.

  --kiosky-player-dir PATH
      Local checkout used to build a git archive from the pinned commit. Defaults
      to /home/builder/kiosky-player. Only tracked files at the pinned commit are
      archived; private config, .env and secret-like names are refused.

  --local-out-dir /tmp/...

Rules:
  - host is an argument, never hardcoded;
  - never touches the dev board;
  - never reads or copies config from the dev board;
  - never embeds secrets, Wi-Fi credentials, IP/MAC/DNS/gateway or hostname;
  - never changes Wi-Fi/NetworkManager;
  - never calls writer except --provision-real-config, which is intentionally
    blocked unless a future restricted private-values path is added;
  - never reboots without the exact reboot confirmation phrase;
  - writes sanitized artifacts under /tmp.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect-base) MODE="inspect-base" ;;
    --install-dry-run) MODE="install-dry-run" ;;
    --install-apply) MODE="install-apply" ;;
    --verify) MODE="verify" ;;
    --idempotence-check) MODE="idempotence-check" ;;
    --config-missing-check) MODE="config-missing-check" ;;
    --f10-check) MODE="f10-check" ;;
    --reboot-check) MODE="reboot-check" ;;
    --provision-real-config) MODE="provision-real-config" ;;
    --install-runtime) INSTALL_RUNTIME=1 ;;
    --kiosky-player-dir)
      shift
      KIOSKY_PLAYER_DIR="${1:-}"
      ;;
    --local-out-dir)
      shift
      LOCAL_OUT_DIR="${1:-}"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      HOST="$1"
      ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect-base|install-dry-run|install-apply|verify|idempotence-check|config-missing-check|f10-check|reboot-check|provision-real-config) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ -z "$HOST" ]; then
  echo "error: host is required; pass it explicitly, for example root@<second-board-host>" >&2
  exit 2
fi

case "$LOCAL_OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --local-out-dir must be under /tmp" >&2; exit 2 ;;
esac

if [ "$INSTALL_RUNTIME" -eq 1 ] && [ "$MODE" != "install-apply" ]; then
  echo "error: --install-runtime is only valid with --install-apply" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BOARD_DIR="$REPO_ROOT/scripts/board"
INSTALLER="$BOARD_DIR/install_totem_appliance.sh"
VERIFIER="$BOARD_DIR/verify_totem_appliance.sh"
MANIFEST="$BOARD_DIR/totem_appliance_manifest.json"
APP_ARCHIVE="$LOCAL_OUT_DIR/kiosky-player-pinned.tar.gz"
APP_ARCHIVE_LIST="$LOCAL_OUT_DIR/kiosky-player-archive-list.txt"
APP_PIN_JSON="$LOCAL_OUT_DIR/kiosky-player-pin.json"
SSH_CONTROL_DIR="/tmp/dadooh-c10-9-ssh-$TIMESTAMP"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/%C"
LOCAL_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || printf unknown)"
LOCAL_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || printf unknown)"
LOCAL_DIRTY_COUNT="$(git -C "$REPO_ROOT" status --short 2>/dev/null | wc -l | tr -d ' ')"

ssh_board() {
  mkdir -p "$SSH_CONTROL_DIR"
  chmod 700 "$SSH_CONTROL_DIR"
  ssh -o ConnectTimeout=10 -o NumberOfPasswordPrompts=1 -o ControlMaster=auto -o ControlPersist=300 -o ControlPath="$SSH_CONTROL_PATH" "$HOST" "$@"
}

scp_board() {
  mkdir -p "$SSH_CONTROL_DIR"
  chmod 700 "$SSH_CONTROL_DIR"
  scp -o ConnectTimeout=10 -o NumberOfPasswordPrompts=1 -o ControlMaster=auto -o ControlPersist=300 -o ControlPath="$SSH_CONTROL_PATH" "$@"
}

expected_manifest_value() {
  python3 - "$MANIFEST" "$1" <<'PY'
import json
import pathlib
import sys

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
value = manifest["kiosky_player"].get(sys.argv[2], "")
print(value)
PY
}

write_runner_summary() {
  local result="$1"
  cat > "$LOCAL_OUT_DIR/README.md" <<EOF
# C10.9 remote runner artifact

- mode: \`$MODE\`
- result: \`$result\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- source_dirty_entries: \`$LOCAL_DIRTY_COUNT\`
- host: \`<second-board-host>\`
- remote_workspace: \`/tmp/dadooh-c10-9-second-board-clean-install/...\`
- secrets_published: \`false\`
- config_content_read: \`false\`
- dev_board_touched: \`false\`
- dev_config_copied: \`false\`
- writer_called: \`false\`
- network_changed: \`false\`
- packages_installed: \`false\`
- reboot_called: \`false\`

Artifacts copied from the board are under \`remote/\` and are expected to be
sanitized JSON/text only.
EOF
  chmod 600 "$LOCAL_OUT_DIR/README.md"
}

prepare_app_archive() {
  local expected_commit expected_ref expected_repo archive_sha
  expected_commit="$(expected_manifest_value expected_commit)"
  expected_ref="$(expected_manifest_value expected_ref)"
  expected_repo="$(expected_manifest_value repo_full_name)"

  if [ ! -d "$KIOSKY_PLAYER_DIR/.git" ]; then
    echo "error: kiosky-player checkout not found or not a git repo: $KIOSKY_PLAYER_DIR" >&2
    exit 3
  fi
  git -C "$KIOSKY_PLAYER_DIR" cat-file -e "$expected_commit^{commit}"
  git -C "$KIOSKY_PLAYER_DIR" archive --format=tar.gz --output "$APP_ARCHIVE" "$expected_commit"
  tar -tzf "$APP_ARCHIVE" > "$APP_ARCHIVE_LIST"
  python3 - "$APP_ARCHIVE_LIST" <<'PY'
import pathlib
import sys

allowed_config = {"config.example.json", "config.appliance.example.json"}
bad = []
for raw in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    name = raw.strip()
    if not name:
        continue
    parts = pathlib.PurePosixPath(name).parts
    base = parts[-1] if parts else name
    lowered = base.lower()
    if name.startswith("/") or ".." in parts:
        bad.append("unsafe_path")
    elif lowered in {"config.json", "config.local.json"} and base not in allowed_config:
        bad.append("private_config_name")
    elif lowered.startswith(".env"):
        bad.append("env_name")
    elif "secret" in lowered:
        bad.append("secret_like_name")
if bad:
    print("error: kiosky-player archive refused: " + ",".join(sorted(set(bad))), file=sys.stderr)
    sys.exit(4)
PY
  archive_sha="$(sha256sum "$APP_ARCHIVE" | awk '{print $1}')"
  python3 - "$APP_PIN_JSON" "$expected_repo" "$expected_ref" "$expected_commit" "$archive_sha" <<'PY'
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
payload = {
    "schema_version": "dadooh-c10.9-kiosky-player-pin.v1",
    "repo_full_name": sys.argv[2],
    "ref": sys.argv[3],
    "commit": sys.argv[4],
    "archive_sha256": sys.argv[5],
    "archive_source": "local_git_archive_from_pinned_commit",
    "private_values_included": False,
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  chmod 600 "$APP_ARCHIVE" "$APP_ARCHIVE_LIST" "$APP_PIN_JSON"
}

prepare_local() {
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  bash -n "$INSTALLER"
  bash -n "$VERIFIER"
  bash -n "$0"
  python3 -m json.tool "$MANIFEST" >/dev/null
  "$VERIFIER" --self-test
  "$INSTALLER" --manifest --out-dir "$LOCAL_OUT_DIR/local-manifest" >/dev/null
  prepare_app_archive
}

copy_repo_subset() {
  ssh_board "rm -rf '$REMOTE_REPO' '$REMOTE_OUT_DIR' '$REMOTE_APP_ARCHIVE' '$REMOTE_APP_PIN' && mkdir -p '$REMOTE_REPO' '$REMOTE_OUT_DIR' '$REMOTE_ROOT' && chmod 700 '$REMOTE_ROOT' '$REMOTE_REPO' '$REMOTE_OUT_DIR'"
  tar -C "$REPO_ROOT" -czf - scripts/board scripts/remote docs/product/02_ROADMAP_IMPLEMENTACAO_PRODUTO.md docs/product/85_REPRODUTIBILIDADE_PLACA_PARA_IMAGEM.md docs/product/86_C10_8_INSTALADOR_IDEMPOTENTE_APPLIANCE.md docs/product/87_C10_8_1_RESOLUCAO_DELTAS_REPRODUTIBILIDADE.md \
    | ssh_board "tar -C '$REMOTE_REPO' -xzf -"
  scp_board -q "$APP_ARCHIVE" "$HOST:$REMOTE_APP_ARCHIVE"
  scp_board -q "$APP_PIN_JSON" "$HOST:$REMOTE_APP_PIN"
  ssh_board "printf '%s\n' '$LOCAL_HEAD' > '$REMOTE_REPO/.orange_pi_totem_head' && printf '%s\n' '$LOCAL_BRANCH' > '$REMOTE_REPO/.orange_pi_totem_branch' && printf '%s\n' '$LOCAL_DIRTY_COUNT' > '$REMOTE_REPO/.orange_pi_totem_dirty_entries' && chmod 600 '$REMOTE_REPO/.orange_pi_totem_head' '$REMOTE_REPO/.orange_pi_totem_branch' '$REMOTE_REPO/.orange_pi_totem_dirty_entries' '$REMOTE_APP_ARCHIVE' '$REMOTE_APP_PIN'"
}

remote_prepare_checks() {
  ssh_board "REMOTE_REPO='$REMOTE_REPO' REMOTE_APP_ARCHIVE='$REMOTE_APP_ARCHIVE' REMOTE_APP_PIN='$REMOTE_APP_PIN' bash -s" <<'REMOTE'
set -euo pipefail
cd "$REMOTE_REPO"
bash -n scripts/board/install_totem_appliance.sh
bash -n scripts/board/verify_totem_appliance.sh
bash -n scripts/remote/run_c10_9_second_board_clean_install.sh
python3 -m json.tool scripts/board/totem_appliance_manifest.json >/dev/null
scripts/board/verify_totem_appliance.sh --self-test
test -s "$REMOTE_APP_ARCHIVE"
test -s "$REMOTE_APP_PIN"
tar -tzf "$REMOTE_APP_ARCHIVE" >/dev/null
python3 -m json.tool "$REMOTE_APP_PIN" >/dev/null
REMOTE
}

pull_remote_artifacts() {
  mkdir -p "$LOCAL_OUT_DIR/remote"
  chmod 700 "$LOCAL_OUT_DIR/remote"
  scp_board -q -r "$HOST:$REMOTE_OUT_DIR/." "$LOCAL_OUT_DIR/remote/" || true
}

prepare_remote_workspace() {
  prepare_local
  copy_repo_subset
  remote_prepare_checks
}

remote_inspect_base() {
  ssh_board "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_OUT_DIR/inspect-base"
chmod 700 "$REMOTE_OUT_DIR/inspect-base"
python3 - "$REMOTE_OUT_DIR/inspect-base/base.json" "$REMOTE_OUT_DIR/inspect-base/summary.txt" <<'PY'
import json
import pathlib
import subprocess
import time

json_out = pathlib.Path(__import__("sys").argv[1])
summary_out = pathlib.Path(__import__("sys").argv[2])


def run(args, timeout=6):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=6):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


def file_text(path):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""


def parse_key_file(path, allowed):
    data = {}
    for line in file_text(path).splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in allowed:
            data[key] = value.strip().strip('"')
    return data


def pkg_present(name):
    result = run(["dpkg-query", "-W", "-f=${Status}", name], 5)
    return bool(result is not None and result.returncode == 0 and (result.stdout or "").strip() == "install ok installed")


def command_present(name):
    return bool(out(["sh", "-c", "command -v " + name], 4))


def service_state(name):
    return {
        "active": out(["systemctl", "is-active", name], 5) or "unknown",
        "enabled": out(["systemctl", "is-enabled", name], 5) or "unknown",
    }


required_commands = ["python3", "mpv", "ffmpeg", "nmcli"]
required_packages = ["mpv", "ffmpeg", "python3-requests", "network-manager"]
forbidden_commands = ["Xorg", "chromium", "chromium-browser", "weston"]
forbidden_packages = ["xserver-xorg", "chromium", "chromium-browser", "weston"]
system_failed_raw = out(["systemctl", "--failed", "--no-legend", "--plain"], 8)
system_failed_count = 0 if not system_failed_raw else len([line for line in system_failed_raw.splitlines() if line.strip()])
armbian = parse_key_file("/etc/armbian-release", {"BOARD", "BOARD_NAME", "VERSION", "BRANCH"})
os_release = parse_key_file("/etc/os-release", {"ID", "VERSION_ID", "VERSION_CODENAME", "PRETTY_NAME"})
board_model = file_text("/proc/device-tree/model")
forbidden_present = {name: command_present(name) for name in forbidden_commands}
forbidden_pkg_present = {name: pkg_present(name) for name in forbidden_packages}
runtime_commands = {name: command_present(name) for name in required_commands}
runtime_packages = {name: pkg_present(name) for name in required_packages}
base_compatible = not any(forbidden_present.values()) and not any(forbidden_pkg_present.values()) and command_present("systemctl") and command_present("dpkg-query")
if os_release.get("ID") and os_release.get("ID") != "debian":
    base_compatible = False
base_drift_from_dev = "unknown"
if board_model and "OrangePi Zero3" not in board_model and "Orange Pi Zero 3" not in board_model:
    base_drift_from_dev = "true"
elif os_release.get("VERSION_CODENAME") and os_release.get("VERSION_CODENAME") != "bookworm":
    base_drift_from_dev = "true"
elif board_model or os_release.get("VERSION_CODENAME"):
    base_drift_from_dev = "false"
payload = {
    "schema_version": "dadooh-c10.9-inspect-base.v1",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "rules": {
        "read_only": True,
        "hostname_published": False,
        "network_identifiers_published": False,
        "logs_collected": False,
        "config_content_read": False,
    },
    "system": {
        "board_model": board_model or "unknown",
        "kernel": out(["uname", "-r"], 5) or "unknown",
        "armbian": armbian,
        "debian": os_release,
        "systemctl_failed_count": system_failed_count,
    },
    "networkmanager": {
        "package_present": pkg_present("network-manager"),
        "nmcli_present": command_present("nmcli"),
        "service": service_state("NetworkManager.service"),
    },
    "runtime": {
        "commands": runtime_commands,
        "packages": runtime_packages,
        "forbidden_commands_present": forbidden_present,
        "forbidden_packages_present": forbidden_pkg_present,
    },
    "totem_user_exists": run(["id", "totem"], 4) is not None and run(["id", "totem"], 4).returncode == 0,
    "totem_group_exists": run(["getent", "group", "totem"], 4) is not None and run(["getent", "group", "totem"], 4).returncode == 0,
    "paths": {
        "/opt/totem": pathlib.Path("/opt/totem").exists(),
        "/data": pathlib.Path("/data").exists(),
    },
    "base_compatible": base_compatible,
    "base_drift_from_dev": base_drift_from_dev,
}
json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
json_out.chmod(0o600)
lines = [
    "C10.9 inspect-base summary",
    f"base_compatible={str(base_compatible).lower()}",
    f"base_drift_from_dev={base_drift_from_dev}",
    f"systemctl_failed_count={system_failed_count}",
    f"networkmanager_present={str(payload['networkmanager']['package_present']).lower()}",
    "runtime_missing_commands=" + ",".join(k for k, v in runtime_commands.items() if not v),
    "runtime_missing_packages=" + ",".join(k for k, v in runtime_packages.items() if not v),
    f"totem_user_exists={str(payload['totem_user_exists']).lower()}",
    f"opt_totem_exists={str(payload['paths']['/opt/totem']).lower()}",
    f"data_exists={str(payload['paths']['/data']).lower()}",
]
summary_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
summary_out.chmod(0o600)
print(f"inspect_base_json={json_out}")
print(f"summary={summary_out}")
print(f"base_compatible={str(base_compatible).lower()}")
PY
REMOTE
}

remote_app_preflight() {
  local name="$1"
  ssh_board "REMOTE_REPO='$REMOTE_REPO' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_APP_PIN='$REMOTE_APP_PIN' NAME='$name' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_OUT_DIR/$NAME"
chmod 700 "$REMOTE_OUT_DIR/$NAME"
python3 - "$REMOTE_REPO/scripts/board/totem_appliance_manifest.json" "$REMOTE_APP_PIN" "$REMOTE_OUT_DIR/$NAME/kiosky-player.json" "$REMOTE_OUT_DIR/$NAME/kiosky-player-summary.txt" <<'PY'
import json
import pathlib
import subprocess
import sys
import time

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
pin = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
json_out = pathlib.Path(sys.argv[3])
summary_out = pathlib.Path(sys.argv[4])
spec = manifest["kiosky_player"]
app = pathlib.Path(spec["install_path"])
entrypoint = app / "kiosk.py"
marker = pathlib.Path("/data/state/totem-appliance/kiosky-player-installed.json")


def run(args, timeout=6):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=6):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


marker_data = {}
marker_parse_ok = False
if marker.exists() and not marker.is_symlink():
    try:
        raw = json.loads(marker.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            marker_data = {key: raw.get(key) for key in ("repo_full_name", "ref", "commit", "archive_sha256", "private_values_included")}
            marker_parse_ok = True
    except Exception:
        marker_parse_ok = False

has_git = (app / ".git").exists()
git_head = out(["git", "-C", str(app), "rev-parse", "HEAD"], 8) if has_git else "unknown"
expected_commit = spec.get("expected_commit")
marker_ok = (
    marker_parse_ok
    and marker_data.get("commit") == expected_commit
    and marker_data.get("ref") == spec.get("expected_ref")
    and marker_data.get("repo_full_name") in {spec.get("repo_full_name"), spec.get("expected_repo")}
    and marker_data.get("private_values_included") is False
)
git_ok = has_git and git_head == expected_commit
entrypoint_ok = entrypoint.exists() and entrypoint.is_file() and not entrypoint.is_symlink()
deploy_required = not (entrypoint_ok and (marker_ok or git_ok))
payload = {
    "schema_version": "dadooh-c10.9-kiosky-player-preflight.v1",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "rules": {
        "config_content_read": False,
        "private_values_included": False,
        "dev_board_used": False,
    },
    "install_path_exists": app.exists(),
    "entrypoint_present": entrypoint_ok,
    "git_metadata_present": has_git,
    "git_head": git_head,
    "marker_present": marker.exists(),
    "marker_parse_ok": marker_parse_ok,
    "marker_public_fields": marker_data,
    "expected_commit": expected_commit,
    "archive_sha256": pin.get("archive_sha256"),
    "verification_level": "git_head" if git_ok else ("installed_marker" if marker_ok else "missing_or_unverified"),
    "pin_ok": entrypoint_ok and (marker_ok or git_ok),
    "deploy_required": deploy_required,
}
json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
json_out.chmod(0o600)
summary_out.write_text(
    "\n".join(
        [
            "C10.9 kiosky-player preflight summary",
            f"entrypoint_present={str(entrypoint_ok).lower()}",
            f"git_metadata_present={str(has_git).lower()}",
            f"marker_present={str(marker.exists()).lower()}",
            f"pin_ok={str(payload['pin_ok']).lower()}",
            f"deploy_required={str(deploy_required).lower()}",
            f"verification_level={payload['verification_level']}",
        ]
    )
    + "\n",
    encoding="utf-8",
)
summary_out.chmod(0o600)
print(f"kiosky_player_json={json_out}")
print(f"summary={summary_out}")
print(f"deploy_required={str(deploy_required).lower()}")
PY
REMOTE
}

remote_install_app_archive() {
  ssh_board "REMOTE_REPO='$REMOTE_REPO' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_APP_ARCHIVE='$REMOTE_APP_ARCHIVE' REMOTE_APP_PIN='$REMOTE_APP_PIN' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_OUT_DIR/install-app"
chmod 700 "$REMOTE_OUT_DIR/install-app"
python3 - "$REMOTE_REPO/scripts/board/totem_appliance_manifest.json" "$REMOTE_APP_PIN" "$REMOTE_OUT_DIR/install-app/preflight.json" <<'PY'
import json
import pathlib
import sys

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
pin = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
out = pathlib.Path(sys.argv[3])
spec = manifest["kiosky_player"]
payload = {
    "schema_version": "dadooh-c10.9-install-app-preflight.v1",
    "expected_commit": spec.get("expected_commit"),
    "archive_commit": pin.get("commit"),
    "pin_match": spec.get("expected_commit") == pin.get("commit"),
    "private_values_included": pin.get("private_values_included") is True,
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if not payload["pin_match"] or payload["private_values_included"]:
    sys.exit(12)
PY
if python3 - "$REMOTE_REPO/scripts/board/totem_appliance_manifest.json" "$REMOTE_APP_PIN" "$REMOTE_OUT_DIR/install-app/apply.json" <<'PY'
import json
import pathlib
import sys
import time

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
pin = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
out = pathlib.Path(sys.argv[3])
spec = manifest["kiosky_player"]
app = pathlib.Path(spec["install_path"])
marker = pathlib.Path("/data/state/totem-appliance/kiosky-player-installed.json")
entrypoint = app / "kiosk.py"
marker_ok = False
if marker.exists() and not marker.is_symlink():
    try:
        raw = json.loads(marker.read_text(encoding="utf-8"))
        marker_ok = (
            isinstance(raw, dict)
            and raw.get("repo_full_name") in {spec.get("repo_full_name"), spec.get("expected_repo")}
            and raw.get("ref") == spec.get("expected_ref")
            and raw.get("commit") == spec.get("expected_commit")
            and raw.get("archive_sha256") == pin.get("archive_sha256")
            and raw.get("private_values_included") is False
        )
    except Exception:
        marker_ok = False
if entrypoint.exists() and marker_ok:
    payload = {
        "schema_version": "dadooh-c10.9-install-app-apply.v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "skipped_already_installed",
        "installed_from": "pinned_git_archive",
        "archive_sha256": pin.get("archive_sha256"),
        "private_values_included": False,
        "dev_board_used": False,
        "config_created": False,
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sys.exit(0)
sys.exit(1)
PY
then
  printf 'app_install_status=skipped_already_installed\n'
  exit 0
fi
python3 - "$REMOTE_APP_ARCHIVE" <<'PY'
import pathlib
import subprocess
import sys

archive = pathlib.Path(sys.argv[1])
result = subprocess.run(["tar", "-tzf", str(archive)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
if result.returncode != 0:
    print("archive_list_failed", file=sys.stderr)
    sys.exit(13)
allowed_config = {"config.example.json", "config.appliance.example.json"}
bad = []
for raw in result.stdout.splitlines():
    name = raw.strip()
    if not name:
        continue
    parts = pathlib.PurePosixPath(name).parts
    base = parts[-1] if parts else name
    lowered = base.lower()
    if name.startswith("/") or ".." in parts:
        bad.append("unsafe_path")
    elif lowered in {"config.json", "config.local.json"} and base not in allowed_config:
        bad.append("private_config_name")
    elif lowered.startswith(".env"):
        bad.append("env_name")
    elif "secret" in lowered:
        bad.append("secret_like_name")
if bad:
    print("archive_refused=" + ",".join(sorted(set(bad))), file=sys.stderr)
    sys.exit(14)
PY
target="/opt/totem/kiosky-player"
state_dir="/data/state/totem-appliance"
if find "$target" -maxdepth 1 -type f \( -name 'config.json' -o -name 'config.local.json' -o -name '.env*' -o -iname '*secret*' \) 2>/dev/null | grep -q .; then
  echo "error: refusing to replace app target with private-like files present" >&2
  exit 15
fi
install -d -m 0755 -o root -g root "$target" "$state_dir"
find "$target" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
tar -xzf "$REMOTE_APP_ARCHIVE" -C "$target"
chown -R root:root "$target"
find "$target" -type d -exec chmod 0755 {} +
find "$target" -type f -exec chmod 0644 {} +
python3 - "$REMOTE_REPO/scripts/board/totem_appliance_manifest.json" "$REMOTE_APP_PIN" "$state_dir/kiosky-player-installed.json" <<'PY'
import json
import pathlib
import sys
import time

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
pin = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
out = pathlib.Path(sys.argv[3])
spec = manifest["kiosky_player"]
payload = {
    "schema_version": "dadooh-c10.9-kiosky-player-installed.v1",
    "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "repo_full_name": spec.get("repo_full_name") or spec.get("expected_repo"),
    "ref": spec.get("expected_ref"),
    "commit": spec.get("expected_commit"),
    "archive_sha256": pin.get("archive_sha256"),
    "install_path": spec.get("install_path"),
    "installed_from_pin": True,
    "private_values_included": False,
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
out.chmod(0o644)
PY
python3 - "$REMOTE_OUT_DIR/install-app/apply.json" "$REMOTE_APP_PIN" <<'PY'
import json
import pathlib
import sys
import time

pin = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
payload = {
    "schema_version": "dadooh-c10.9-install-app-apply.v1",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "status": "applied",
    "installed_from": "pinned_git_archive",
    "archive_sha256": pin.get("archive_sha256"),
    "private_values_included": False,
    "dev_board_used": False,
    "config_created": False,
}
pathlib.Path(sys.argv[1]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
printf 'app_install_status=applied\n'
REMOTE
}

run_installer_remote() {
  local installer_mode="$1"
  local name="$2"
  shift 2
  ssh_board "cd '$REMOTE_REPO' && scripts/board/install_totem_appliance.sh '$installer_mode' --repo-root '$REMOTE_REPO' --out-dir '$REMOTE_OUT_DIR/$name' $*"
}

remote_config_missing_check() {
  ssh_board "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_OUT_DIR/config-missing-check"
chmod 700 "$REMOTE_OUT_DIR/config-missing-check"
python3 - "$REMOTE_OUT_DIR/config-missing-check/config-missing.json" "$REMOTE_OUT_DIR/config-missing-check/summary.txt" <<'PY'
import json
import pathlib
import subprocess
import time
import sys

json_out = pathlib.Path(sys.argv[1])
summary_out = pathlib.Path(sys.argv[2])


def run(args, timeout=6):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=6):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


def load_public_json(path, allowed):
    p = pathlib.Path(path)
    if not p.exists() or p.is_symlink():
        return {}, False
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}, False
    if not isinstance(raw, dict):
        return {}, False
    return {key: raw.get(key) for key in allowed}, True


def proc_count(pattern):
    result = run(["pgrep", "-fc", pattern], 5)
    if result is None or result.returncode not in {0, 1}:
        return 0
    try:
        return int((result.stdout or "0").strip() or "0")
    except ValueError:
        return 0


launcher, launcher_parse = load_public_json(
    "/data/state/kiosky-player/launcher-status.json",
    {"state", "config_state", "config_missing", "display_connected", "service_state"},
)
player, player_parse = load_public_json(
    "/tmp/kiosky-status.json",
    {"player_state", "playback_state", "mpv_running", "error_code", "config_state", "config_missing"},
)
config_present = pathlib.Path("/data/config/config.json").exists()
launcher_state = str(launcher.get("state") or "").lower()
player_state = str(player.get("player_state") or "").lower()
playback_state = str(player.get("playback_state") or "").lower()
if config_present:
    public_state = "config_present"
elif launcher_state in {"config_missing", "setup_local_requested", "setup_local_starting", "setup_local_running", "setup_local_cancelled"}:
    public_state = "config_missing"
elif player.get("config_missing") is True or launcher.get("config_missing") is True:
    public_state = "config_missing"
elif launcher_state == "stopped":
    public_state = "maintenance_placeholder"
else:
    public_state = launcher_state or "unknown"
system_failed_raw = out(["systemctl", "--failed", "--no-legend", "--plain"], 8)
system_failed_count = 0 if not system_failed_raw else len([line for line in system_failed_raw.splitlines() if line.strip()])
services = {
    name: {
        "active": out(["systemctl", "is-active", name], 5) or "unknown",
        "enabled": out(["systemctl", "is-enabled", name], 5) or "unknown",
        "nrestarts": out(["systemctl", "show", name, "-p", "NRestarts", "--value"], 5) or "unknown",
    }
    for name in ("kiosky-player.service", "totem-settings-trigger.service", "totem-open-settings.service", "dadooh-visual-splash.service")
}
counts = {
    "kiosk_process_count": proc_count("kiosk.py"),
    "mpv_process_count": proc_count("[m]pv"),
    "setup_process_count": proc_count("totem_setup_visual_wizard.py|totem_setup_local_wizard.py"),
}
safe = (
    not config_present
    and public_state in {"config_missing", "maintenance_placeholder", "unknown"}
    and counts["setup_process_count"] == 0
)
payload = {
    "schema_version": "dadooh-c10.9-config-missing-check.v1",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "rules": {
        "config_content_read": False,
        "secrets_published": False,
        "network_changed": False,
        "writer_called": False,
    },
    "config_real_present": config_present,
    "public_state": public_state,
    "launcher_status_parse_ok": launcher_parse,
    "launcher_public_fields": launcher,
    "player_status_parse_ok": player_parse,
    "player_public_fields": player,
    "player_state": player_state or "unknown",
    "playback_state": playback_state or "unknown",
    "services": services,
    "process_counts": counts,
    "systemctl_failed_count": system_failed_count,
    "config_missing_safe": safe,
}
json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
json_out.chmod(0o600)
summary_out.write_text(
    "\n".join(
        [
            "C10.9 config-missing check summary",
            f"config_real_present={str(config_present).lower()}",
            f"public_state={public_state}",
            f"player_state={player_state or 'unknown'}",
            f"playback_state={playback_state or 'unknown'}",
            f"systemctl_failed_count={system_failed_count}",
            f"setup_process_count={counts['setup_process_count']}",
            f"mpv_process_count={counts['mpv_process_count']}",
            f"config_missing_safe={str(safe).lower()}",
        ]
    )
    + "\n",
    encoding="utf-8",
)
summary_out.chmod(0o600)
print(f"config_missing_json={json_out}")
print(f"summary={summary_out}")
print(f"config_missing_safe={str(safe).lower()}")
PY
REMOTE
}

remote_f10_check() {
  ssh_board "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' F10_WAIT_SEC='$F10_WAIT_SEC' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_OUT_DIR/f10-check"
chmod 700 "$REMOTE_OUT_DIR/f10-check"
python3 - "$REMOTE_OUT_DIR/f10-check/f10.json" "$REMOTE_OUT_DIR/f10-check/summary.txt" "$F10_WAIT_SEC" <<'PY'
import json
import pathlib
import subprocess
import sys
import time

json_out = pathlib.Path(sys.argv[1])
summary_out = pathlib.Path(sys.argv[2])
wait_sec = int(sys.argv[3])


def out(args, timeout=5):
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
        return (result.stdout or "").strip()
    except Exception:
        return ""


def snapshot():
    return {
        "open_settings_active": out(["systemctl", "is-active", "totem-open-settings.service"]) or "unknown",
        "open_settings_enabled": out(["systemctl", "is-enabled", "totem-open-settings.service"]) or "unknown",
        "player_active": out(["systemctl", "is-active", "kiosky-player.service"]) or "unknown",
        "trigger_active": out(["systemctl", "is-active", "totem-settings-trigger.service"]) or "unknown",
        "session_lock_present": pathlib.Path("/run/dadooh-settings/session.lock").exists(),
        "request_present": pathlib.Path("/run/dadooh-settings/request.json").exists(),
    }


before = snapshot()
opened = False
closed_after_open = False
deadline = time.time() + wait_sec
samples = []
while time.time() < deadline:
    current = snapshot()
    samples.append(current)
    if current["open_settings_active"] in {"active", "activating"}:
        opened = True
    if opened and current["open_settings_active"] in {"inactive", "failed"} and not current["session_lock_present"]:
        closed_after_open = True
        break
    time.sleep(2)
after = snapshot()
passed = opened and closed_after_open and not after["session_lock_present"] and not after["request_present"]
payload = {
    "schema_version": "dadooh-c10.9-f10-check.v1",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "operator_assisted": True,
    "instructions": "human pressed and cancelled F10 flow; runner only observed sanitized states",
    "writer_called_by_runner": False,
    "config_content_read": False,
    "before": before,
    "after": after,
    "opened": opened,
    "closed_after_open": closed_after_open,
    "sample_count": len(samples),
    "passed": passed,
}
json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
json_out.chmod(0o600)
summary_out.write_text(
    "\n".join(
        [
            "C10.9 F10 check summary",
            "operator_assisted=true",
            f"opened={str(opened).lower()}",
            f"closed_after_open={str(closed_after_open).lower()}",
            f"session_lock_present_after={str(after['session_lock_present']).lower()}",
            f"request_present_after={str(after['request_present']).lower()}",
            f"passed={str(passed).lower()}",
        ]
    )
    + "\n",
    encoding="utf-8",
)
summary_out.chmod(0o600)
print(f"f10_json={json_out}")
print(f"summary={summary_out}")
print(f"passed={str(passed).lower()}")
sys.exit(0 if passed else 21)
PY
REMOTE
}

wait_for_ssh_after_reboot() {
  local deadline now
  deadline=$((SECONDS + REBOOT_WAIT_SEC))
  sleep 8
  while [ "$SECONDS" -lt "$deadline" ]; do
    if ssh_board "true" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  return 1
}

run_prepare_only() {
  prepare_remote_workspace
  write_runner_summary "prepare-only-ok"
  pull_remote_artifacts
  printf 'prepare_only_artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_inspect_base() {
  prepare_remote_workspace
  remote_inspect_base
  pull_remote_artifacts
  write_runner_summary "inspect-base-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_install_dry_run() {
  prepare_remote_workspace
  remote_inspect_base
  remote_app_preflight "install-dry-run-app"
  run_installer_remote "--dry-run" "install-dry-run"
  pull_remote_artifacts
  write_runner_summary "install-dry-run-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_install_apply() {
  echo
  echo "This will install the appliance layer on the second board from the repo copy and deploy kiosky-player from the pinned git archive."
  echo "It will not create private config, copy dev-board state, call writer, change Wi-Fi, reboot, or run apt upgrade."
  if [ "$INSTALL_RUNTIME" -eq 1 ]; then
    echo "Runtime package install is enabled: explicit apt-get install --no-install-recommends may be used for manifest runtime packages."
  fi
  echo "Type exactly:"
  echo "$INSTALL_CONFIRM_PHRASE"
  printf '> '
  IFS= read -r typed
  if [ "$typed" != "$INSTALL_CONFIRM_PHRASE" ]; then
    echo "confirmation_mismatch" >&2
    exit 20
  fi

  prepare_remote_workspace
  remote_inspect_base
  remote_app_preflight "install-apply-app-before"
  if [ "$INSTALL_RUNTIME" -eq 1 ]; then
    run_installer_remote "--apply" "install-apply" "--install-runtime"
  else
    run_installer_remote "--apply" "install-apply"
  fi
  remote_install_app_archive
  remote_app_preflight "install-apply-app-after"
  pull_remote_artifacts
  write_runner_summary "install-apply-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_verify() {
  prepare_remote_workspace
  remote_app_preflight "verify-app"
  run_installer_remote "--verify" "verify"
  pull_remote_artifacts
  write_runner_summary "verify-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_idempotence_check() {
  prepare_remote_workspace
  remote_app_preflight "idempotence-app"
  run_installer_remote "--idempotence-check" "idempotence-check"
  pull_remote_artifacts
  write_runner_summary "idempotence-check-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_config_missing_check() {
  prepare_remote_workspace
  remote_config_missing_check
  pull_remote_artifacts
  write_runner_summary "config-missing-check-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_f10_check() {
  echo
  echo "This is an operator-assisted observer. A human at the second board must hold F10 and cancel settings while the runner watches sanitized state."
  echo "The runner does not start the settings service, call writer, read config, or change Wi-Fi."
  echo "Type exactly:"
  echo "$F10_CONFIRM_PHRASE"
  printf '> '
  IFS= read -r typed
  if [ "$typed" != "$F10_CONFIRM_PHRASE" ]; then
    echo "confirmation_mismatch" >&2
    exit 20
  fi
  prepare_remote_workspace
  remote_f10_check
  pull_remote_artifacts
  write_runner_summary "f10-check-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_reboot_check() {
  echo
  echo "This will reboot the second board and then re-copy the sanitized runner workspace to verify state."
  echo "Type exactly:"
  echo "$REBOOT_CONFIRM_PHRASE"
  printf '> '
  IFS= read -r typed
  if [ "$typed" != "$REBOOT_CONFIRM_PHRASE" ]; then
    echo "confirmation_mismatch" >&2
    exit 20
  fi
  prepare_remote_workspace
  ssh_board "systemctl reboot" || true
  rm -rf "$SSH_CONTROL_DIR"
  if ! wait_for_ssh_after_reboot; then
    echo "error: ssh did not return after reboot within ${REBOOT_WAIT_SEC}s" >&2
    exit 22
  fi
  prepare_remote_workspace
  remote_inspect_base
  remote_app_preflight "reboot-check-app"
  run_installer_remote "--verify" "reboot-check-verify"
  remote_config_missing_check
  pull_remote_artifacts
  write_runner_summary "reboot-check-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_provision_real_config() {
  echo
  echo "Type exactly:"
  echo "$PROVISION_CONFIRM_PHRASE"
  printf '> '
  IFS= read -r typed
  if [ "$typed" != "$PROVISION_CONFIRM_PHRASE" ]; then
    echo "confirmation_mismatch" >&2
    exit 20
  fi
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  cat > "$LOCAL_OUT_DIR/provision-real-config-blocked.txt" <<'EOF'
C10.9 base runner intentionally does not accept private values yet.
Provisioning real config must be added with a restricted /tmp private-values
argument and a no-stdout policy before calling writer.
EOF
  chmod 600 "$LOCAL_OUT_DIR/provision-real-config-blocked.txt"
  write_runner_summary "provision-real-config-blocked"
  echo "provision_real_config_blocked_requires_private_values_file" >&2
  exit 23
}

case "$MODE" in
  prepare-only) run_prepare_only ;;
  inspect-base) run_inspect_base ;;
  install-dry-run) run_install_dry_run ;;
  install-apply) run_install_apply ;;
  verify) run_verify ;;
  idempotence-check) run_idempotence_check ;;
  config-missing-check) run_config_missing_check ;;
  f10-check) run_f10_check ;;
  reboot-check) run_reboot_check ;;
  provision-real-config) run_provision_real_config ;;
esac
