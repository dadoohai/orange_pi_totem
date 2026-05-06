#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
TIMESTAMP="${C11_1_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c11-1-read-only-policy-probe}"
LOCAL_OUT_DIR="${C11_1_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c11-1-read-only-policy-mitigation}"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/dadooh-c11-1-read-only-policy-probe}"
REMOTE_WORK="$REMOTE_ROOT/work-$TIMESTAMP"
REMOTE_OUT="$REMOTE_ROOT/out-$TIMESTAMP"
SSH_CONTROL_DIR="/tmp/dadooh-c11-1-ssh-$TIMESTAMP"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/%C"

usage() {
  cat <<'USAGE'
Usage:
  run_c11_1_read_only_policy_probe.sh <root@host> [mode] [options]

Modes:
  --prepare-only
  --probe-dev
  --summary

Options:
  --local-out-dir /tmp/...

Rules:
  - read-only policy probe only;
  - dev board only for C11.1;
  - host is an argument, never hardcoded;
  - does not enable read-only, remount, reboot, poweroff, call writer, edit
    config, edit Wi-Fi/NetworkManager, install packages or restart services;
  - never stores raw logs, config content, secrets, SSID, IP, MAC, DNS,
    profile names or payloads.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --probe-dev) MODE="probe-dev" ;;
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
  prepare-only|probe-dev|summary) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ "$MODE" = "probe-dev" ] && [ -z "$HOST" ]; then
  echo "error: host is required for --probe-dev" >&2
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
  bash -n "$REPO_ROOT/scripts/remote/run_c11_1_read_only_policy_probe.sh"
  bash -n "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh"
  python3 -m json.tool "$REPO_ROOT/scripts/board/totem_read_only_policy.json" >/dev/null
  "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh" --self-test >/dev/null
  "$REPO_ROOT/scripts/board/verify_totem_appliance.sh" --self-test >/dev/null
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
# C11.1 read-only policy probe runner artifact

- mode: \`$MODE\`
- result: \`$result\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- source_dirty_entries: \`$LOCAL_DIRTY_COUNT\`
- host: \`<board-host>\`
- remote_workspace: \`/tmp/dadooh-c11-1-read-only-policy-probe/...\`
- read_only_enabled: \`false\`
- poweroff_executed: \`false\`
- reboot_executed: \`false\`
- writer_called: \`false\`
- real_config_read: \`false\`
- real_config_written: \`false\`
- wifi_changed: \`false\`
- networkmanager_changed: \`false\`
- packages_installed: \`false\`
- raw_logs_published: \`false\`
- secrets_published: \`false\`
EOF
  chmod 600 "$LOCAL_OUT_DIR/README.md"
}

pull_remote_artifacts() {
  mkdir -p "$LOCAL_OUT_DIR/remote"
  chmod 700 "$LOCAL_OUT_DIR/remote"
  scp_board -q -r "$HOST:$REMOTE_OUT/." "$LOCAL_OUT_DIR/remote/" || true
}

run_probe_dev() {
  prepare_local
  ssh_board "mkdir -p '$REMOTE_WORK' '$REMOTE_OUT' && chmod 700 '$REMOTE_ROOT' '$REMOTE_WORK' '$REMOTE_OUT'"
  scp_board -q \
    "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh" \
    "$REPO_ROOT/scripts/board/totem_read_only_policy.json" \
    "$HOST:$REMOTE_WORK/"
  ssh_board "chmod 700 '$REMOTE_WORK/verify_totem_read_only_policy.sh' && '$REMOTE_WORK/verify_totem_read_only_policy.sh' --policy '$REMOTE_WORK/totem_read_only_policy.json' --out-dir '$REMOTE_OUT'"
  pull_remote_artifacts
  write_local_readme "probe-dev-complete"
}

write_summary_from_latest() {
  prepare_local
  mkdir -p "$LOCAL_OUT_DIR/summary"
  chmod 700 "$LOCAL_OUT_DIR/summary"
  python3 - "$LOCAL_RUN_ROOT" "$LOCAL_OUT_DIR/summary/read-only-policy-summary.json" "$LOCAL_OUT_DIR/summary/summary.txt" <<'PY'
import json
import pathlib
import sys
import time

root = pathlib.Path(sys.argv[1])
out_json = pathlib.Path(sys.argv[2])
out_txt = pathlib.Path(sys.argv[3])
probes = []
for path in sorted(root.glob("*-c11-1-read-only-policy-mitigation/remote/read-only-policy-verify.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    probes.append(
        {
            "policy_schema_version": data.get("policy_schema_version"),
            "root_read_only_ready": data.get("root_read_only_ready"),
            "ready_for_read_only_enablement": data.get("ready_for_read_only_enablement"),
            "ready_for_c11_2_enablement": data.get("ready_for_c11_2_enablement"),
            "blockers_remaining_count": len(data.get("blockers_remaining", [])),
            "networkmanager_policy": data.get("networkmanager", {}).get("classification", "UNKNOWN"),
            "journald_policy": data.get("journald", {}).get("classification", "UNKNOWN"),
        }
    )
payload = {
    "schema_version": "dadooh-c11.1-read-only-policy-summary.v1",
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "probes_found": len(probes),
    "probes": probes,
    "read_only_enabled": False,
    "poweroff_executed": False,
    "reboot_executed": False,
    "writer_called": False,
    "wifi_changed": False,
    "networkmanager_changed": False,
    "packages_installed": False,
    "raw_logs_published": False,
    "secrets_published": False,
}
out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
out_json.chmod(0o600)
lines = [
    "C11.1 read-only policy summary",
    f"probes_found: {len(probes)}",
    "read_only_enabled: false",
    "poweroff_executed: false",
    "reboot_executed: false",
    "writer_called: false",
    "wifi_changed: false",
    "networkmanager_changed: false",
    "packages_installed: false",
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
  probe-dev)
    run_probe_dev
    ;;
  summary)
    write_summary_from_latest
    ;;
esac
