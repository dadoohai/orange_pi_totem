#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
TIMESTAMP="${C11_0_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c11-0-read-only-readiness-audit}"
LOCAL_OUT_DIR="${C11_0_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c11-0-read-only-readiness-audit}"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/dadooh-c11-0-read-only-readiness-audit}"
REMOTE_OUT="$REMOTE_ROOT/out-$TIMESTAMP"
SSH_CONTROL_DIR="/tmp/dadooh-c11-0-ssh-$TIMESTAMP"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/%C"

usage() {
  cat <<'USAGE'
Usage:
  run_c11_0_read_only_readiness_audit.sh <root@host> [mode] [options]

Modes:
  --prepare-only
  --audit-dev
  --audit-test-readonly
  --summary

Options:
  --local-out-dir /tmp/...

Rules:
  - read-only audit only;
  - host is an argument, never hardcoded;
  - audit dev first; test board is optional and uses the same read-only collector;
  - does not enable read-only, poweroff, reboot, call writer, edit config, edit Wi-Fi, install packages or restart services;
  - never stores raw logs, config content, secrets, SSID, IP, MAC, DNS or payloads.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --audit-dev) MODE="audit-dev" ;;
    --audit-test-readonly) MODE="audit-test-readonly" ;;
    --summary) MODE="summary" ;;
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
  prepare-only|audit-dev|audit-test-readonly|summary) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ "$MODE" != "prepare-only" ] && [ -z "$HOST" ]; then
  echo "error: host is required for $MODE" >&2
  exit 2
fi

case "$LOCAL_OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --local-out-dir must be under /tmp" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
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

prepare_local() {
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  git -C "$REPO_ROOT" diff --check
  bash -n "$REPO_ROOT/scripts/remote/run_c11_0_read_only_readiness_audit.sh"
  bash -n "$REPO_ROOT/scripts/board/install_totem_appliance.sh"
  bash -n "$REPO_ROOT/scripts/board/verify_totem_appliance.sh"
  python3 -m json.tool "$REPO_ROOT/scripts/board/totem_appliance_manifest.json" >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_wifi_nm_adapter.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_config_contract_validate.py" --self-test >/dev/null
}

write_local_readme() {
  local result="$1"
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  cat > "$LOCAL_OUT_DIR/README.md" <<EOF
# C11.0 read-only readiness audit runner artifact

- mode: \`$MODE\`
- result: \`$result\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- source_dirty_entries: \`$LOCAL_DIRTY_COUNT\`
- host: \`<board-host>\`
- remote_workspace: \`/tmp/dadooh-c11-0-read-only-readiness-audit/...\`
- read_only_enabled: \`false\`
- poweroff_executed: \`false\`
- reboot_executed: \`false\`
- writer_called: \`false\`
- real_config_read: \`false\`
- real_config_written: \`false\`
- wifi_changed: \`false\`
- packages_installed: \`false\`
- raw_logs_published: \`false\`
- secrets_published: \`false\`
EOF
}

pull_remote_artifacts() {
  mkdir -p "$LOCAL_OUT_DIR/remote"
  chmod 700 "$LOCAL_OUT_DIR/remote"
  scp_board -q -r "$HOST:$REMOTE_OUT/." "$LOCAL_OUT_DIR/remote/" || true
}

run_remote_audit() {
  local board_role="$1"
  prepare_local
  ssh_board "mkdir -p '$REMOTE_OUT' && chmod 700 '$REMOTE_ROOT' '$REMOTE_OUT'"
  ssh_board "BOARD_ROLE='$board_role' OUT_JSON='$REMOTE_OUT/readiness-audit.json' OUT_SUMMARY='$REMOTE_OUT/summary.txt' python3 -" <<'PY'
import json
import os
import pathlib
import stat
import subprocess
import time

CLASS_OK = "OK_FOR_READ_ONLY"
CLASS_DATA = "NEEDS_DATA_PATH"
CLASS_TMP = "NEEDS_TMP_PATH"
CLASS_VAR = "NEEDS_VAR_POLICY"
CLASS_ETC = "NEEDS_ETC_EXCEPTION"
CLASS_NM = "NEEDS_NETWORKMANAGER_POLICY"
CLASS_LOG = "NEEDS_LOG_POLICY"
CLASS_BLOCKER = "BLOCKER"
CLASS_UNKNOWN = "UNKNOWN"


def run(args, timeout=8):
    try:
        return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=8):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


def exists(path):
    p = pathlib.Path(path)
    return p.exists() and not p.is_symlink()


def stat_meta(path):
    p = pathlib.Path(path)
    payload = {"path": path, "exists": p.exists(), "is_symlink": p.is_symlink()}
    if not p.exists() or p.is_symlink():
        return payload
    try:
        st = p.stat()
    except OSError:
        payload["stat_available"] = False
        return payload
    payload.update(
        {
            "type": "dir" if p.is_dir() else ("file" if p.is_file() else "other"),
            "mode": f"{stat.S_IMODE(st.st_mode):04o}",
        }
    )
    return payload


def unit_state(name):
    nrestarts = out(["systemctl", "show", name, "-p", "NRestarts", "--value"])
    return {
        "active": out(["systemctl", "is-active", name]) or "unknown",
        "enabled": out(["systemctl", "is-enabled", name]) or "unknown",
        "nrestarts": int(nrestarts) if nrestarts.isdigit() else None,
    }


def first_json(paths):
    for raw in paths:
        path = pathlib.Path(raw)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    return {}


def process_counts():
    counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmdline = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
        except Exception:
            continue
        if not cmdline:
            continue
        if "kiosk.py" in cmdline or "/opt/totem/kiosky-player" in cmdline:
            counts["player"] += 1
        if "mpv" in cmdline:
            counts["mpv"] += 1
        if "totem_status_renderer" in cmdline or "totem_status_render_preview.py" in cmdline:
            counts["renderer"] += 1
        if "totem_setup_visual_wizard.py" in cmdline or "totem_open_settings_session.sh" in cmdline:
            counts["setup"] += 1
    return counts


def failed_count():
    text = out(["systemctl", "list-units", "--failed", "--no-legend", "--no-pager"], timeout=10)
    return len([line for line in text.splitlines() if line.strip()])


def classify_path(path, purpose):
    if path.startswith("/data/") or path == "/data":
        return CLASS_DATA
    if path.startswith("/tmp/") or path == "/tmp":
        return CLASS_TMP
    if path.startswith("/run/") or path == "/run":
        return CLASS_OK
    if path.startswith("/var/log") or "journal" in path.lower() or "log" in purpose.lower():
        return CLASS_LOG
    if path.startswith("/var/"):
        return CLASS_VAR
    if path.startswith("/etc/NetworkManager"):
        return CLASS_NM
    if path.startswith("/etc/"):
        return CLASS_ETC
    if path.startswith("/boot/"):
        return CLASS_ETC
    if path.startswith("/opt/"):
        return CLASS_OK
    return CLASS_UNKNOWN


def item(name, path, purpose, component, notes=""):
    return {
        "name": name,
        "path": path,
        "component": component,
        "purpose": purpose,
        "classification": classify_path(path, purpose),
        "exists": pathlib.Path(path).exists(),
        "notes": notes,
    }


def nm_profile_audit():
    path = pathlib.Path("/etc/NetworkManager/system-connections")
    profile_count = None
    dedicated_profile_present = "unknown"
    if path.exists() and path.is_dir() and not path.is_symlink():
        try:
            files = [p for p in path.iterdir() if p.is_file() and not p.is_symlink()]
            profile_count = len(files)
            dedicated_profile_present = any(
                p.name.startswith("dadooh-c9-8-") or p.name.startswith("dadooh-product-wifi-") for p in files
            )
        except OSError:
            profile_count = None
    return {
        "profile_path": "/etc/NetworkManager/system-connections",
        "profile_path_exists": path.exists(),
        "profile_count": profile_count,
        "dedicated_profile_present": dedicated_profile_present,
        "stores_ssid_or_credentials": "yes_private_do_not_publish",
        "read_only_classification": CLASS_NM,
        "policy_needed": "Wi-Fi apply/troca de rede exige excecao controlada ou janela root-writable; perfis nao devem ser publicados.",
    }


def journald_audit():
    storage = "default"
    conf = pathlib.Path("/etc/systemd/journald.conf")
    if conf.exists() and not conf.is_symlink():
        try:
            for raw in conf.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if line.startswith("Storage="):
                    storage = line.split("=", 1)[1].strip() or "default"
        except OSError:
            storage = "unknown"
    persistent_dir = pathlib.Path("/var/log/journal")
    return {
        "journald_storage": storage,
        "persistent_journal_dir_present": persistent_dir.exists(),
        "read_only_classification": CLASS_LOG if persistent_dir.exists() or storage in {"persistent", "auto"} else CLASS_OK,
        "policy_needed": "Definir journald volatil ou mover/persistir logs em /data antes de root read-only.",
    }


def mount_audit():
    rows = []
    for target in ("/", "/boot", "/data", "/tmp", "/run", "/var", "/etc"):
        source = out(["findmnt", "-n", "-o", "TARGET,FSTYPE,OPTIONS", "--target", target])
        parts = source.split(None, 2)
        rows.append(
            {
                "target": target,
                "mounted": bool(source),
                "fstype_category": parts[1] if len(parts) > 1 else "unknown",
                "read_only_now": "ro" in (parts[2].split(",") if len(parts) > 2 else []),
            }
        )
    return rows


status = first_json(("/tmp/dadooh-status/status.json", "/data/state/kiosky-player/launcher-status.json"))
player_status = first_json(("/tmp/kiosky-status.json",))
playback = status.get("playback") or status.get("playback_state") or player_status.get("playback_state") or player_status.get("playback") or "unknown"
items = [
    item("config real", "/data/config/config.json", "writer/config real", "writer"),
    item("config backup", "/data/config", "config backup directory", "writer"),
    item("media cache", "/data/media/kiosky-player", "media/cache", "player"),
    item("player state", "/data/state/kiosky-player", "launcher/player state", "player"),
    item("private settings context", "/data/state/totem-settings/last-settings.json", "private settings prefill", "settings"),
    item("orientation contract", "/data/state/totem-display/orientation.json", "public orientation contract", "wizard/splash/player"),
    item("boot visual rollback state", "/data/state/totem-boot-visual", "boot visual rollback state", "installer/guardrails"),
    item("installed manifest", "/data/state/totem-appliance", "installed manifest/state", "installer"),
    item("app logs", "/data/logs/kiosky-player", "app logs", "player"),
    item("runtime dir", "/tmp/kiosky", "runtime ipc/socket", "player/mpv"),
    item("status public tmp", "/tmp/dadooh-status", "public status cache", "status"),
    item("settings trigger runtime", "/run/dadooh-settings", "trigger request/lock", "settings"),
    item("systemd units", "/etc/systemd/system", "unit files installed by package", "installer/systemd"),
    item("networkmanager profiles", "/etc/NetworkManager/system-connections", "Wi-Fi profiles", "NetworkManager"),
    item("journald persistent dir", "/var/log/journal", "system logs", "journald"),
    item("systemd runtime state", "/var/lib/systemd", "systemd persistent state", "systemd"),
    item("networkmanager runtime state", "/var/lib/NetworkManager", "NetworkManager state", "NetworkManager"),
    item("boot args", "/boot/armbianEnv.txt", "boot visual guardrails", "installer/boot"),
]
counts = {}
for row in items:
    counts[row["classification"]] = counts.get(row["classification"], 0) + 1
blockers = []
for row in items:
    if row["classification"] in {CLASS_UNKNOWN, CLASS_BLOCKER}:
        blockers.append(row["name"])
nm = nm_profile_audit()
journald = journald_audit()
if nm["read_only_classification"] == CLASS_NM:
    blockers.append("NetworkManager policy for Wi-Fi profile writes")
if journald["read_only_classification"] == CLASS_LOG:
    blockers.append("journald/log policy")
blockers = sorted(set(blockers))
payload = {
    "schema_version": "dadooh-c11.0-read-only-readiness-audit.v1",
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "board_role": os.environ.get("BOARD_ROLE", "dev"),
    "host": "<board-host>",
    "read_only_enabled": False,
    "poweroff_executed": False,
    "reboot_executed": False,
    "writer_called": False,
    "real_config_read": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
    "raw_logs_published": False,
    "secrets_published": False,
    "services": {
        "kiosky-player.service": unit_state("kiosky-player.service"),
        "totem-settings-trigger.service": unit_state("totem-settings-trigger.service"),
        "dadooh-visual-splash.service": unit_state("dadooh-visual-splash.service"),
    },
    "public_state": status.get("public_state") or status.get("state") or "unknown",
    "playback": playback,
    "process_counts": process_counts(),
    "systemctl_failed_count": failed_count(),
    "mounts": mount_audit(),
    "paths": items,
    "classification_counts": counts,
    "networkmanager": nm,
    "journald": journald,
    "state_contracts": {
        "config_in_data": pathlib.Path("/data/config/config.json").exists(),
        "orientation_json_path": "/data/state/totem-display/orientation.json",
        "settings_request_path": "/run/dadooh-settings/request.json",
        "settings_lock_path": "/run/dadooh-settings/session.lock",
        "visual_splash_state_path": "/data/state/totem-boot-visual",
        "player_runtime_path": "/tmp/kiosky",
        "player_state_path": "/data/state/kiosky-player",
        "player_media_path": "/data/media/kiosky-player",
        "player_logs_path": "/data/logs/kiosky-player",
    },
    "installer_manifest_compatible_paths": True,
    "root_read_only_ready": False,
    "ready_for_read_only_enablement": False,
    "ready_for_c11_1_policy": bool(blockers),
    "ready_for_c11_1": bool(blockers),
    "blockers": blockers,
    "recommendation": "C11.1 pode iniciar como rodada de politica/mitigacao para NetworkManager, journald/var e excecoes; ainda nao habilitar root read-only.",
}
out_json = pathlib.Path(os.environ["OUT_JSON"])
out_summary = pathlib.Path(os.environ["OUT_SUMMARY"])
out_json.parent.mkdir(parents=True, exist_ok=True)
out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
out_json.chmod(0o600)
lines = [
    "C11.0 read-only readiness audit",
    f"board_role: {payload['board_role']}",
    f"root_read_only_ready: {payload['root_read_only_ready']}",
    f"ready_for_read_only_enablement: {payload['ready_for_read_only_enablement']}",
    f"ready_for_c11_1_policy: {payload['ready_for_c11_1_policy']}",
    f"classification_counts: {json.dumps(counts, sort_keys=True)}",
    f"networkmanager_policy: {nm['read_only_classification']}",
    f"journald_policy: {journald['read_only_classification']}",
    f"blockers_count: {len(blockers)}",
    "read_only_enabled: false",
    "poweroff_executed: false",
    "reboot_executed: false",
    "writer_called: false",
    "real_config_read: false",
    "real_config_written: false",
    "wifi_changed: false",
    "raw_logs_published: false",
]
out_summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
out_summary.chmod(0o600)
PY
  pull_remote_artifacts
  write_local_readme "$MODE-complete"
}

write_summary_from_latest() {
  prepare_local
  mkdir -p "$LOCAL_OUT_DIR/summary"
  chmod 700 "$LOCAL_OUT_DIR/summary"
  python3 - "$LOCAL_RUN_ROOT" "$LOCAL_OUT_DIR/summary/readiness-summary.json" "$LOCAL_OUT_DIR/summary/summary.txt" <<'PY'
import json
import pathlib
import sys
import time

root = pathlib.Path(sys.argv[1])
out_json = pathlib.Path(sys.argv[2])
out_txt = pathlib.Path(sys.argv[3])
audits = []
for path in sorted(root.glob("*-c11-0-read-only-readiness-audit/remote/readiness-audit.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    audits.append(
        {
            "board_role": data.get("board_role", "unknown"),
            "root_read_only_ready": data.get("root_read_only_ready"),
            "ready_for_read_only_enablement": data.get("ready_for_read_only_enablement"),
            "ready_for_c11_1_policy": data.get("ready_for_c11_1_policy", data.get("ready_for_c11_1")),
            "classification_counts": data.get("classification_counts", {}),
            "blockers_count": len(data.get("blockers", [])),
            "networkmanager_policy": data.get("networkmanager", {}).get("read_only_classification", "UNKNOWN"),
            "journald_policy": data.get("journald", {}).get("read_only_classification", "UNKNOWN"),
        }
    )
payload = {
    "schema_version": "dadooh-c11.0-read-only-readiness-summary.v1",
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "audits_found": len(audits),
    "audits": audits,
    "read_only_enabled": False,
    "poweroff_executed": False,
    "reboot_executed": False,
    "writer_called": False,
    "wifi_changed": False,
    "secrets_published": False,
    "raw_logs_published": False,
}
out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
out_json.chmod(0o600)
lines = [
    "C11.0 read-only readiness summary",
    f"audits_found: {len(audits)}",
    "read_only_enabled: false",
    "poweroff_executed: false",
    "writer_called: false",
    "wifi_changed: false",
]
out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
out_txt.chmod(0o600)
PY
  write_local_readme "summary-complete"
}

case "$MODE" in
  prepare-only)
    prepare_local
    write_local_readme "prepare-only-complete"
    ;;
  audit-dev)
    run_remote_audit "dev"
    ;;
  audit-test-readonly)
    run_remote_audit "test"
    ;;
  summary)
    write_summary_from_latest
    ;;
esac
