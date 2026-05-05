#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
RUN_ROOT="${RUN_ROOT:-/tmp/dadooh-c10-7-reproducibility-audit}"
TIMESTAMP="${C10_7_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${C10_7_OUT_DIR:-$RUN_ROOT/$TIMESTAMP}"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_7_reproducibility_audit.sh <host> [mode] [--out-dir /tmp/...]

Modes:
  --prepare-only
  --audit-board
  --audit-repo
  --compare
  --summary

The board audit is read-only and writes sanitized artifacts only on the local
machine under /tmp. It does not stop services, change config, call writer,
change NetworkManager, run apt, reboot, or collect raw logs/secrets.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --audit-board) MODE="audit-board" ;;
    --audit-repo) MODE="audit-repo" ;;
    --compare) MODE="compare" ;;
    --summary) MODE="summary" ;;
    --out-dir) shift; OUT_DIR="${1:-}" ;;
    --help|-h) usage; exit 0 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|audit-board|audit-repo|compare|summary) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

case "$OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --out-dir must be under /tmp" >&2; exit 2 ;;
esac

if [ "$MODE" != "audit-repo" ] && [ "$MODE" != "compare" ] && [ -z "$HOST" ]; then
  echo "error: host is required; pass it explicitly, for example root@<board-host>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BOARD_JSON="$OUT_DIR/board-audit.json"
REPO_JSON="$OUT_DIR/repo-audit.json"
COMPARE_JSON="$OUT_DIR/compare.json"
COMPARE_MD="$OUT_DIR/compare.md"
SUMMARY_MD="$OUT_DIR/README.md"

prepare_out_dir() {
  mkdir -p "$OUT_DIR"
  chmod 700 "$OUT_DIR"
}

ssh_ro() {
  ssh -o ConnectTimeout=10 -o NumberOfPasswordPrompts=1 "$HOST" "$@"
}

run_prepare() {
  prepare_out_dir
  bash -n "$0"
  if [ -n "$HOST" ]; then
    ssh_ro "python3 --version >/dev/null && systemctl --version >/dev/null && uname -r >/dev/null"
  fi
  printf 'c10.7 prepare-only: ok\n'
}

run_audit_board() {
  prepare_out_dir
  ssh_ro "python3 -" > "$BOARD_JSON" <<'PY'
import grp
import hashlib
import json
import os
import pathlib
import pwd
import shutil
import stat
import subprocess
import sys

SCRIPTS = [
    "kiosky_service_launcher.sh",
    "totem_config_contract_validate.py",
    "totem_config_writer_real.py",
    "totem_open_settings_session.sh",
    "totem_settings_trigger.py",
    "totem_setup_local_wizard.py",
    "totem_setup_minimal_server.py",
    "totem_setup_visual_wizard.py",
    "totem_status_aggregate.py",
    "totem_status_renderer.sh",
    "totem_visual_setup_writer_handoff.py",
    "totem_visual_splash.py",
    "totem_wifi_local_credentials_tty.py",
    "totem_wifi_nm_adapter.py",
]
UNITS = [
    "kiosky-player.service",
    "totem-settings-trigger.service",
    "totem-open-settings.service",
    "dadooh-visual-splash.service",
]
PATHS = [
    "/opt/totem",
    "/opt/totem/bin",
    "/opt/totem/kiosky-player",
    "/data/config",
    "/data/state",
    "/data/media",
    "/data/logs",
    "/data/state/totem-display",
    "/data/state/totem-boot-visual",
    "/tmp/kiosky",
    "/tmp/dadooh-status",
    "/tmp/kiosky-status.json",
    "/run/dadooh-settings",
]
PACKAGES = ["mpv", "ffmpeg", "python3-requests", "network-manager", "python3", "dbus", "openssh-server"]
FORBIDDEN_PACKAGES = ["xserver-xorg", "chromium", "chromium-browser", "weston"]
WIFI_PREFIXES = ("dadooh-c9-8-", "dadooh-product-wifi-")
KNOWN_WIFI_PROFILE = "dadooh-c9-8-wifi-persistent"


def run(args, timeout=5):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=5):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


def pkg(name):
    result = run(["dpkg-query", "-W", "-f=${Status}\t${Version}", name], 4)
    if result is None or result.returncode != 0:
        return {"present": False, "version": "absent"}
    parts = (result.stdout or "").strip().split("\t")
    present = bool(parts and parts[0] == "install ok installed")
    return {"present": present, "version": parts[1] if present and len(parts) > 1 else "unknown"}


def file_hash(path):
    path = pathlib.Path(path)
    if not path.exists() or not path.is_file() or path.is_symlink():
        return "unavailable"
    try:
        if path.stat().st_size > 1024 * 1024:
            return "skipped_large"
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return "unavailable"


def owner(uid):
    try:
        name = pwd.getpwuid(uid).pw_name
    except KeyError:
        return "other"
    return name if name in {"root", "totem"} else "other"


def group(gid):
    try:
        name = grp.getgrgid(gid).gr_name
    except KeyError:
        return "other"
    return name if name in {"root", "totem", "audio", "video", "render"} else "other"


def stat_meta(raw):
    path = pathlib.Path(raw)
    data = {"exists": path.exists(), "path": raw}
    if not path.exists():
        return data
    try:
        st = path.lstat()
    except OSError:
        data["stat_error"] = True
        return data
    data.update(
        {
            "type": "symlink" if path.is_symlink() else ("dir" if path.is_dir() else "file"),
            "mode": f"{stat.S_IMODE(st.st_mode):04o}",
            "owner_category": owner(st.st_uid),
            "group_category": group(st.st_gid),
        }
    )
    return data


def unit(unit_name):
    active = out(["systemctl", "is-active", unit_name]) or "unknown"
    enabled = out(["systemctl", "is-enabled", unit_name]) or "unknown"
    fragment = out(["systemctl", "show", unit_name, "-p", "FragmentPath", "--value"]) or ""
    return {
        "active": active,
        "enabled": enabled,
        "fragment_path_category": fragment if fragment else "none",
        "unit_hash": file_hash(fragment) if fragment else "unavailable",
    }


def kv_file(path, allowed):
    result = {}
    path = pathlib.Path(path)
    if not path.exists() or path.is_symlink():
        return result
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() in allowed:
            result[key.strip()] = value.strip().strip('"')
    return result


def boot():
    parsed = kv_file("/boot/armbianEnv.txt", {"verbosity", "console", "extraargs"})
    tokens = set(parsed.get("extraargs", "").split())
    data = {
        "armbian_env_exists": pathlib.Path("/boot/armbianEnv.txt").exists(),
        "console_serial_present": parsed.get("console") == "serial" or "console=serial" in tokens,
        "verbosity_0": parsed.get("verbosity") == "0",
        "loglevel_0_present": "loglevel=0" in tokens,
        "rd_systemd_show_status_false_present": "rd.systemd.show_status=false" in tokens,
        "systemd_show_status_false_present": "systemd.show_status=false" in tokens,
        "logo_nologo_present": "logo.nologo" in tokens,
        "quiet_present": "quiet" in tokens,
        "vt_cursor_hidden_present": "vt.global_cursor_default=0" in tokens,
        "rollback_state_present": pathlib.Path("/data/state/totem-boot-visual").exists(),
        "getty_tty1": unit("getty@tty1.service"),
        "getty_tty2": unit("getty@tty2.service"),
    }
    data["early_boot_quiet_guardrails_applied"] = bool(
        data["console_serial_present"]
        and data["verbosity_0"]
        and data["loglevel_0_present"]
        and data["rd_systemd_show_status_false_present"]
        and data["logo_nologo_present"]
    )
    return data


def failed_count():
    raw = out(["systemctl", "--failed", "--no-legend", "--plain"], 8)
    return 0 if not raw else len([line for line in raw.splitlines() if line.strip()])


def processes():
    counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
    self_pid = os.getpid()
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == self_pid:
            continue
        try:
            names = [pathlib.Path(p.decode("utf-8", "ignore")).name.lower() for p in (proc / "cmdline").read_bytes().split(b"\0") if p]
        except OSError:
            continue
        joined = " ".join(names)
        if "kiosk.py" in names:
            counts["player"] += 1
        if "mpv" in names:
            counts["mpv"] += 1
        if "totem_status_renderer.sh" in names or "status_renderer" in joined:
            counts["renderer"] += 1
        if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
            counts["setup"] += 1
    return counts


def public_json(path, fields):
    path = pathlib.Path(path)
    if not path.exists() or path.is_symlink():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {field: data.get(field, "unknown") for field in fields}


def config():
    path = pathlib.Path("/data/config/config.json")
    meta = stat_meta(str(path))
    runner = shutil.which("runuser")

    def test(flag):
        if not path.exists() or not runner:
            return False if not path.exists() else "unknown"
        result = run([runner, "-u", "totem", "--", "test", flag, str(path)], 4)
        return "unknown" if result is None else result.returncode == 0

    write_ok = test("-w")
    return {
        "present": path.exists(),
        "owner_mode_ok": bool(path.exists() and meta.get("owner_category") == "root" and meta.get("group_category") == "totem" and meta.get("mode") == "0640"),
        "totem_read_ok": test("-r"),
        "totem_write_blocked": (not write_ok) if isinstance(write_ok, bool) else "unknown",
        "meta": meta,
    }


def wifi():
    data = {
        "nmcli_present": bool(shutil.which("nmcli")),
        "networkmanager_service": unit("NetworkManager.service"),
        "wifi_connection_count": "unknown",
        "wifi_active_count": "unknown",
        "dedicated_wifi_profile_present": "unknown",
        "persistent_profile_prefix_count": "unknown",
    }
    if not data["nmcli_present"]:
        return data
    raw_types = out(["nmcli", "-t", "-f", "TYPE", "connection", "show"], 8)
    if raw_types:
        data["wifi_connection_count"] = sum(1 for line in raw_types.splitlines() if "wireless" in line.lower() or "wifi" in line.lower())
    raw_active = out(["nmcli", "-t", "-f", "TYPE", "connection", "show", "--active"], 8)
    if raw_active:
        data["wifi_active_count"] = sum(1 for line in raw_active.splitlines() if "wireless" in line.lower() or "wifi" in line.lower())
    known = run(["nmcli", "-t", "-f", "connection.id", "connection", "show", KNOWN_WIFI_PROFILE], 8)
    data["dedicated_wifi_profile_present"] = bool(known is not None and known.returncode == 0)
    raw_names = out(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], 8)
    if raw_names:
        count = 0
        for line in raw_names.splitlines():
            try:
                name, ctype = line.rsplit(":", 1)
            except ValueError:
                continue
            if ("wireless" in ctype.lower() or "wifi" in ctype.lower()) and name.startswith(WIFI_PREFIXES):
                count += 1
        data["persistent_profile_prefix_count"] = count
    return data


def user():
    user_result = run(["id", "totem"], 4)
    group_result = run(["getent", "group", "totem"], 4)
    groups = []
    if user_result is not None and user_result.returncode == 0:
        groups = [part for part in out(["id", "-nG", "totem"], 4).split() if part]
    expected = {name: name in groups for name in ("totem", "audio", "video", "render")}
    return {
        "user_totem_exists": bool(user_result is not None and user_result.returncode == 0),
        "group_totem_exists": bool(group_result is not None and group_result.returncode == 0),
        "totem_groups": groups,
        "expected_group_membership": expected,
    }


def system():
    model = "unknown"
    model_path = pathlib.Path("/proc/device-tree/model")
    if model_path.exists():
        model = model_path.read_text(encoding="utf-8", errors="ignore").replace("\x00", "").strip() or "unknown"
    return {
        "board_model": model,
        "kernel_release": out(["uname", "-r"]) or "unknown",
        "os_release": kv_file("/etc/os-release", {"ID", "VERSION_ID", "VERSION_CODENAME", "PRETTY_NAME"}),
        "armbian_release": kv_file("/etc/armbian-release", {"BOARD", "BOARD_NAME", "VERSION", "BRANCH", "DISTRIBUTION_CODENAME", "IMAGE_TYPE"}),
        "systemctl_failed_count": failed_count(),
    }


def app():
    app_dir = pathlib.Path("/opt/totem/kiosky-player")
    has_git = (app_dir / ".git").exists()
    git_head = out(["git", "-C", str(app_dir), "rev-parse", "HEAD"], 8) if has_git else "unknown"
    return {
        "public_status": public_json("/tmp/dadooh-status/status.json", ["public_state", "state"]),
        "playback_status": public_json("/tmp/kiosky-status.json", ["playback_state", "mpv_running"]),
        "process_counts": processes(),
        "kiosky_player": {
            "path_exists": app_dir.exists(),
            "kiosk_py_present": (app_dir / "kiosk.py").exists(),
            "has_git_metadata": has_git,
            "git_head": git_head or "unknown",
            "kiosk_py_hash": file_hash(app_dir / "kiosk.py"),
        },
    }


forbidden_commands = {
    "chromium": bool(shutil.which("chromium") or shutil.which("chromium-browser")),
    "Xorg": bool(shutil.which("Xorg")),
    "weston": bool(shutil.which("weston")),
}
payload = {
    "schema_version": "dadooh-c10.7-board-reproducibility-audit.v1",
    "audit_rules": {
        "read_only": True,
        "service_state_changed": False,
        "config_read": False,
        "config_written": False,
        "writer_called": False,
        "network_changed": False,
        "apt_called": False,
        "reboot_called": False,
        "raw_logs_collected": False,
        "sensitive_values_published": False,
    },
    "system": system(),
    "packages": {name: pkg(name) for name in PACKAGES},
    "forbidden_runtime": {"commands_present": forbidden_commands, "packages_present": {name: pkg(name)["present"] for name in FORBIDDEN_PACKAGES}},
    "user": user(),
    "paths": {path: stat_meta(path) for path in PATHS},
    "scripts": {name: {**stat_meta(str(pathlib.Path("/opt/totem/bin") / name)), "sha256": file_hash(pathlib.Path("/opt/totem/bin") / name)} for name in SCRIPTS},
    "systemd": {name: unit(name) for name in UNITS},
    "boot_visual": boot(),
    "network": wifi(),
    "config": config(),
    "app": app(),
}
json.dump(payload, sys.stdout, indent=2, sort_keys=True)
sys.stdout.write("\n")
PY
  chmod 600 "$BOARD_JSON"
  printf 'board audit written: %s\n' "$BOARD_JSON"
}

run_audit_repo() {
  prepare_out_dir
  python3 - "$REPO_ROOT" > "$REPO_JSON" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys

repo = pathlib.Path(sys.argv[1])


def git(args):
    return subprocess.run(["git", *args], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False).stdout


def sha(path):
    path = pathlib.Path(path)
    if not path.exists() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        return "unavailable"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha_head(rel):
    result = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    return hashlib.sha256(result.stdout).hexdigest() if result.returncode == 0 else "unavailable"


tracked = [p for p in git(["ls-files", "-z"]).split("\0") if p]
tracked_set = set(tracked)
status = [line for line in git(["status", "--short"]).splitlines() if line.strip()]
dirty_paths = [line[3:] for line in status if len(line) > 3]
board = sorted(p for p in tracked if p.startswith("scripts/board/"))
remote = sorted(p for p in tracked if p.startswith("scripts/remote/"))
units = sorted(p for p in tracked if p.endswith(".service"))
docs_product = sorted(p for p in tracked if p.startswith("docs/product/"))
release_docs = sorted(p for p in tracked if p.startswith("docs/releases/") or p.startswith("releases/"))
config_examples = sorted(p for p in tracked if p.endswith(".example.json") or ("config." in pathlib.Path(p).name and pathlib.Path(p).suffix == ".json"))
install_like = sorted(p for p in tracked if p.startswith("scripts/board/setup_") or pathlib.Path(p).name.startswith("deploy_") or "provision" in pathlib.Path(p).name.lower())
boot_guardrail = sorted(p for p in tracked if "c10_5" in pathlib.Path(p).name.lower() or "boot" in pathlib.Path(p).name.lower() or "guard" in pathlib.Path(p).name.lower())
wizard_writer_trigger = sorted(p for p in tracked if any(token in pathlib.Path(p).name for token in ("wizard", "splash", "writer", "trigger", "open_settings")))

board_artifacts = {}
for rel in board:
    board_artifacts[pathlib.Path(rel).name] = {
        "path": rel,
        "tracked": rel in tracked_set,
        "dirty": rel in dirty_paths,
        "worktree_sha256": sha(repo / rel),
        "head_sha256": sha_head(rel),
    }

unit_artifacts = {}
for rel in units:
    unit_artifacts[pathlib.Path(rel).name] = {
        "path": rel,
        "tracked": rel in tracked_set,
        "dirty": rel in dirty_paths,
        "worktree_sha256": sha(repo / rel),
        "head_sha256": sha_head(rel),
    }

payload = {
    "schema_version": "dadooh-c10.7-repo-reproducibility-audit.v1",
    "git": {
        "branch": git(["rev-parse", "--abbrev-ref", "HEAD"]).strip(),
        "head": git(["rev-parse", "HEAD"]).strip(),
        "status_short": status,
        "dirty_paths": dirty_paths,
    },
    "counts": {
        "scripts_board": len(board),
        "scripts_remote": len(remote),
        "systemd_units": len(units),
        "docs_product": len(docs_product),
        "release_docs": len(release_docs),
        "config_examples": len(config_examples),
        "install_like_scripts": len(install_like),
    },
    "files": {
        "scripts_board": board,
        "scripts_remote": remote,
        "systemd_units": units,
        "docs_product": docs_product,
        "release_docs": release_docs,
        "config_examples": config_examples,
        "install_like_scripts": install_like,
        "boot_guardrail_scripts_docs": boot_guardrail,
        "wizard_splash_writer_trigger": wizard_writer_trigger,
    },
    "board_artifacts_by_basename": board_artifacts,
    "unit_artifacts_by_basename": unit_artifacts,
    "capabilities": {
        "has_setup_totem_user": "scripts/board/setup_totem_user.sh" in tracked_set,
        "has_setup_data_layout": "scripts/board/setup_data_layout.sh" in tracked_set,
        "has_setup_app_dirs": "scripts/board/setup_app_dirs.sh" in tracked_set,
        "has_runtime_prereq_check": "scripts/board/check_app_prereqs.sh" in tracked_set,
        "has_deploy_kiosky_player": "scripts/remote/deploy_kiosky_player.sh" in tracked_set,
        "has_persistent_trigger_runner": "scripts/remote/run_c10_6_1_persistent_settings_trigger.sh" in tracked_set,
        "has_boot_quiet_runner": "scripts/remote/run_c10_5_3_early_boot_visual_audit.sh" in tracked_set,
        "has_visual_guard_runner": "scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh" in tracked_set,
        "has_idempotent_appliance_installer": any("install" in pathlib.Path(p).name.lower() and "appliance" in pathlib.Path(p).name.lower() for p in tracked),
        "has_kiosky_player_pinned_ref_manifest": any("kiosky" in p.lower() and ("manifest" in p.lower() or "lock" in p.lower()) for p in tracked),
    },
}
json.dump(payload, sys.stdout, indent=2, sort_keys=True)
sys.stdout.write("\n")
PY
  chmod 600 "$REPO_JSON"
  printf 'repo audit written: %s\n' "$REPO_JSON"
}

run_compare() {
  prepare_out_dir
  if [ ! -f "$BOARD_JSON" ] || [ ! -f "$REPO_JSON" ]; then
    echo "error: missing board-audit.json or repo-audit.json in $OUT_DIR" >&2
    exit 3
  fi
  python3 - "$BOARD_JSON" "$REPO_JSON" "$COMPARE_JSON" "$COMPARE_MD" <<'PY'
import json
import pathlib
import sys

board = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
repo = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
compare_json = pathlib.Path(sys.argv[3])
compare_md = pathlib.Path(sys.argv[4])


def yn(value):
    if value is True:
        return "sim"
    if value is False:
        return "nao"
    if value in (None, "", "unknown"):
        return "desconhecido"
    return str(value)


def add(rows, item, board_present, repo_present, scriptable, private, classification, action):
    rows.append({
        "item": item,
        "presente_na_placa": yn(board_present),
        "presente_no_repo": yn(repo_present),
        "reproduzivel_por_script_hoje": yn(scriptable),
        "privado_nao_entra_na_imagem": yn(private),
        "classificacao": classification,
        "acao_necessaria": action,
    })


rows = []
caps = repo.get("capabilities", {})
packages = board.get("packages", {})
paths = board.get("paths", {})
scripts = board.get("scripts", {})
repo_scripts = repo.get("board_artifacts_by_basename", {})
units = board.get("systemd", {})
repo_units = repo.get("unit_artifacts_by_basename", {})
boot = board.get("boot_visual", {})
network = board.get("network", {})
config = board.get("config", {})
app = board.get("app", {})
user = board.get("user", {})

runtime_present = all(packages.get(name, {}).get("present") is True for name in ("mpv", "ffmpeg", "python3-requests", "network-manager"))
forbidden_present = any(board.get("forbidden_runtime", {}).get("commands_present", {}).values()) or any(board.get("forbidden_runtime", {}).get("packages_present", {}).values())
add(rows, "Base OS Armbian/Debian minimal e kernel", bool(board.get("system", {}).get("kernel_release")), True, False, False, "FALTA_SCRIPT_INSTALACAO", "C10.8 deve transformar a fundacao documentada em instalador/manifest verificavel.")
add(rows, "Runtime minimo mpv/ffmpeg/python3-requests/NetworkManager", runtime_present, caps.get("has_runtime_prereq_check"), False, False, "FALTA_SCRIPT_INSTALACAO", "Existe check/versionamento parcial; falta instalacao idempotente sem apt upgrade.")
add(rows, "Ausencia de desktop/Chromium/Xorg/Wayland/compositor", not forbidden_present, True, False, False, "FALTA_SCRIPT_INSTALACAO", "C10.8 deve validar pacote proibido ausente e nao instalar camada grafica.")
add(rows, "Usuario e grupo totem", user.get("user_totem_exists") and user.get("group_totem_exists"), caps.get("has_setup_totem_user"), caps.get("has_setup_totem_user"), False, "OK_VERSIONADO", "Incluir no instalador idempotente e validar grupos esperados.")
add(rows, "Grupos esperados do usuario totem", all(user.get("expected_group_membership", {}).get(g) for g in ("totem", "audio", "video", "render")), caps.get("has_setup_totem_user"), caps.get("has_setup_totem_user"), False, "OK_VERSIONADO", "Garantir audio/video/render no C10.8.")
add(rows, "Layout /data config/media/state/logs", all(paths.get(p, {}).get("exists") for p in ("/data/config", "/data/media", "/data/state", "/data/logs")), caps.get("has_setup_data_layout") or caps.get("has_setup_app_dirs"), caps.get("has_setup_app_dirs"), False, "OK_VERSIONADO", "Consolidar permissoes finais no instalador.")
add(rows, "Permissoes root:totem 0640 da config real", config.get("owner_mode_ok"), True, False, True, "ESTADO_PRIVADO_NAO_IMAGEM", "Nao embutir config; C10.8 deve apenas criar diretorio/permissoes e validar metadados.")

script_checks = []
script_dirty = []
for name, meta in scripts.items():
    repo_meta = repo_scripts.get(name, {})
    if meta.get("exists") and repo_meta:
        script_checks.append(meta.get("sha256") == repo_meta.get("head_sha256"))
        script_dirty.append(bool(repo_meta.get("dirty")))
scripts_all_match_head = bool(script_checks) and all(script_checks)
scripts_class = "OK_VERSIONADO" if scripts_all_match_head and not any(script_dirty) else "POSSIVEL_DRIFT_PLACA"
add(rows, "/opt/totem/bin scripts allowlisted", sum(1 for meta in scripts.values() if meta.get("exists")), all(name in repo_scripts for name in scripts), scripts_all_match_head, False, scripts_class, "Comparar hashes; commitar mudancas locais ou redeployar a partir de HEAD antes da segunda placa." if scripts_class != "OK_VERSIONADO" else "Hashes da placa batem com HEAD.")

for unit_name in ("kiosky-player.service", "totem-settings-trigger.service", "totem-open-settings.service"):
    unit = units.get(unit_name, {})
    repo_meta = repo_units.get(unit_name, {})
    board_present = unit.get("fragment_path_category") not in {"none", "", None}
    match_head = board_present and repo_meta and unit.get("unit_hash") == repo_meta.get("head_sha256")
    classification = "OK_VERSIONADO" if match_head and not repo_meta.get("dirty") else "POSSIVEL_DRIFT_PLACA"
    add(rows, f"Systemd {unit_name}", board_present, bool(repo_meta), match_head, False, classification, "Revisar unit instalada versus repo/HEAD; ha risco de estado de placa ou worktree local nao commitado." if classification != "OK_VERSIONADO" else "Unit instalada bate com HEAD.")

visual_unit = units.get("dadooh-visual-splash.service", {})
visual_repo_meta = repo_units.get("dadooh-visual-splash.service", {})
visual_board_present = visual_unit.get("fragment_path_category") not in {"none", "", None}
visual_match_head = bool(visual_board_present and visual_repo_meta and visual_unit.get("unit_hash") == visual_repo_meta.get("head_sha256"))
add(rows, "Systemd dadooh-visual-splash.service", visual_board_present, bool(visual_repo_meta), visual_match_head, False, "FALTA_SCRIPT_INSTALACAO" if visual_board_present and not visual_repo_meta else ("OK_VERSIONADO" if visual_match_head else "POSSIVEL_DRIFT_PLACA"), "Unit visual existe na placa, mas nao ha arquivo .service standalone versionado; C10.8 deve versionar ou gerar deterministicamente.")

add(rows, "Trigger F10 persistente", units.get("totem-settings-trigger.service", {}).get("active") == "active" and units.get("totem-settings-trigger.service", {}).get("enabled") == "enabled", caps.get("has_persistent_trigger_runner"), caps.get("has_persistent_trigger_runner"), False, "OK_VERSIONADO", "Incluir instalacao/habilitacao no C10.8.")
add(rows, "Guardrails visuais boot/shutdown/transicao", boot.get("rollback_state_present"), caps.get("has_visual_guard_runner"), caps.get("has_visual_guard_runner"), False, "OK_VERSIONADO", "Transformar runner reversivel em etapa idempotente do instalador.")
add(rows, "Early boot quiet em /boot/armbianEnv.txt", boot.get("early_boot_quiet_guardrails_applied"), caps.get("has_boot_quiet_runner"), caps.get("has_boot_quiet_runner"), False, "OK_VERSIONADO", "C10.8 deve aplicar/validar console=serial, verbosity=0 e flags allowlisted.")
add(rows, "Wi-Fi dedicado persistente", network.get("dedicated_wifi_profile_present"), True, False, True, "ESTADO_PRIVADO_NAO_IMAGEM", "Nao entra na imagem; fica para provisionamento de campo/local sem publicar SSID/senha.")
add(rows, "Config real /data/config/config.json", config.get("present"), True, False, True, "ESTADO_PRIVADO_NAO_IMAGEM", "Nao entra na imagem; criar somente exemplo sanitizado e fluxo de escrita protegido.")
add(rows, "Secrets api_key/api_url/environment_id/station_id", False, True, False, True, "NAO_DEVE_ENTRAR_IMAGEM", "Manter fora de repo, imagem e artefatos; usar handoff privado temporario.")
add(rows, "Midias/cache em /data/media", paths.get("/data/media", {}).get("exists"), True, False, True, "ESTADO_PRIVADO_NAO_IMAGEM", "Nao clonar midias da placa; baixar/sincronizar em runtime.")
add(rows, "Estado/logs runtime em /data/state e /data/logs", paths.get("/data/state", {}).get("exists") and paths.get("/data/logs", {}).get("exists"), True, False, True, "ESTADO_TEMPORARIO", "Criar diretorios; nao copiar conteudo runtime/logs brutos para imagem.")
add(rows, "kiosky-player em /opt/totem/kiosky-player", app.get("kiosky_player", {}).get("path_exists"), caps.get("has_deploy_kiosky_player"), False, False, "FALTA_SCRIPT_INSTALACAO", "Deploy existe, mas C10.8 precisa fixar commit/ref e manifest.")
add(rows, "Commit/ref fixado do kiosky-player", app.get("kiosky_player", {}).get("git_head") not in {"unknown", "", None}, caps.get("has_kiosky_player_pinned_ref_manifest"), False, False, "FALTA_SCRIPT_INSTALACAO", "Registrar origem e ref exatos; preferir manifest de release ou submodule/lock.")
public_status = app.get("public_status", {})
public_state_value = public_status.get("public_state")
if public_state_value in {None, "", "unknown"}:
    public_state_value = public_status.get("state")
add(rows, "Player public_state/playback apos reboot", public_state_value == "player_running" and app.get("playback_status", {}).get("playback_state") == "playing", True, False, False, "ESTADO_TEMPORARIO", "Validar por smoke curto no C10.8; nao copiar status runtime.")
add(rows, "Read-only/root overlay e corte seco", False, False, False, False, "NAO_DEVE_ENTRAR_IMAGEM", "Fora desta rodada; so depois do instalador idempotente e homologacao.")
add(rows, "Instalador idempotente unico do appliance", False, caps.get("has_idempotent_appliance_installer"), caps.get("has_idempotent_appliance_installer"), False, "FALTA_SCRIPT_INSTALACAO", "Este e o escopo direto de C10.8.")

payload = {
    "schema_version": "dadooh-c10.7-reproducibility-comparison.v1",
    "rows": rows,
    "conclusion": {
        "fully_reproducible_today": False,
        "second_board_ready_by_script_today": False,
        "main_blocker": "Falta instalador idempotente C10.8 e pin explicito do kiosky-player; estados privados nao devem entrar na imagem.",
    },
}
compare_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
compare_json.chmod(0o600)
headers = ["Item", "Presente na placa", "Presente no repo", "Reproduzivel por script hoje", "Privado/nao entra na imagem", "Classificacao", "Acao necessaria"]
lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
for row in rows:
    values = [row["item"], row["presente_na_placa"], row["presente_no_repo"], row["reproduzivel_por_script_hoje"], row["privado_nao_entra_na_imagem"], row["classificacao"], row["acao_necessaria"]]
    lines.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in values) + " |")
compare_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
compare_md.chmod(0o600)
PY
  printf 'comparison written: %s\n' "$COMPARE_MD"
}

run_summary() {
  run_audit_board
  run_audit_repo
  run_compare
  python3 - "$BOARD_JSON" "$REPO_JSON" "$COMPARE_JSON" "$SUMMARY_MD" <<'PY'
import json
import pathlib
import sys

board = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
repo = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
compare = json.loads(pathlib.Path(sys.argv[3]).read_text(encoding="utf-8"))
target = pathlib.Path(sys.argv[4])
counts = {}
for row in compare["rows"]:
    counts[row["classificacao"]] = counts.get(row["classificacao"], 0) + 1
public_status = board.get("app", {}).get("public_status", {})
public_state = public_status.get("public_state")
if public_state in {None, "", "unknown"}:
    public_state = public_status.get("state", "unknown")
lines = [
    "# C10.7 Reproducibility Audit",
    "",
    "Sanitized read-only audit. No config contents, secrets, network identifiers, raw logs, backups, payloads, IPs, MACs, DNS, gateway, hostname or SSID are included.",
    "",
    "## Snapshot",
    "",
    f"- repo_branch: `{repo.get('git', {}).get('branch', 'unknown')}`",
    f"- repo_head: `{repo.get('git', {}).get('head', 'unknown')}`",
    f"- repo_dirty_entries: `{len(repo.get('git', {}).get('status_short', []))}`",
    f"- systemctl_failed_count: `{board.get('system', {}).get('systemctl_failed_count', 'unknown')}`",
    f"- public_state: `{public_state}`",
    f"- playback: `{board.get('app', {}).get('playback_status', {}).get('playback_state', 'unknown')}`",
    "- fully_reproducible_today: `false`",
    "- second_board_ready_by_script_today: `false`",
    "",
    "## Classification Counts",
    "",
]
for key in sorted(counts):
    lines.append(f"- {key}: `{counts[key]}`")
lines.extend(["", "## Artifacts", "", "- `board-audit.json`", "- `repo-audit.json`", "- `compare.json`", "- `compare.md`", "", "## Conclusion", "", compare["conclusion"]["main_blocker"]])
target.write_text("\n".join(lines) + "\n", encoding="utf-8")
target.chmod(0o600)
print(target.read_text(encoding="utf-8"))
PY
}

case "$MODE" in
  prepare-only) run_prepare ;;
  audit-board) run_audit_board ;;
  audit-repo) run_audit_repo ;;
  compare) run_compare ;;
  summary) run_summary ;;
esac
