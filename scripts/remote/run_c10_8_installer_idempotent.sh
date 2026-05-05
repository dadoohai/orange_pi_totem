#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
TIMESTAMP="${C10_8_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c10-8-installer-idempotent}"
LOCAL_OUT_DIR="${C10_8_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c10-8-installer-idempotent}"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/dadooh-c10-8-installer-idempotent}"
REMOTE_REPO="$REMOTE_ROOT/repo-$TIMESTAMP"
REMOTE_OUT_DIR="$REMOTE_ROOT/out-$TIMESTAMP"
APPLY_CONFIRM_PHRASE="CONFIRMO APPLY REFRESH INSTALLER C10.8.1 NA PLACA DEV"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_8_installer_idempotent.sh <host> [mode]

Modes:
  --prepare-only
  --dry-run-dev
  --verify-dev
  --idempotence-dev-dry-run
  --apply-dev-refresh

Rules:
  - host is an argument, never hardcoded;
  - copies a sanitized repo subset to /tmp on the board;
  - does not touch the second board/card;
  - does not stop player by default;
  - does not change real config;
  - does not call writer;
  - does not change Wi-Fi/NetworkManager;
  - does not install packages without explicit installer flag;
  - does not reboot;
  - writes sanitized artifacts under /tmp.

--apply-dev-refresh requires typing the exact confirmation phrase shown by the
runner. Without that mode, the runner is read-only on the board apart from /tmp
workspace/artifacts.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --dry-run-dev) MODE="dry-run-dev" ;;
    --verify-dev) MODE="verify-dev" ;;
    --idempotence-dev-dry-run) MODE="idempotence-dev-dry-run" ;;
    --apply-dev-refresh) MODE="apply-dev-refresh" ;;
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
  prepare-only|dry-run-dev|verify-dev|idempotence-dev-dry-run|apply-dev-refresh) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ -z "$HOST" ]; then
  echo "error: host is required; pass it explicitly, for example root@<board-host>" >&2
  exit 2
fi

case "$LOCAL_OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --local-out-dir must be under /tmp" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BOARD_DIR="$REPO_ROOT/scripts/board"
INSTALLER="$BOARD_DIR/install_totem_appliance.sh"
VERIFIER="$BOARD_DIR/verify_totem_appliance.sh"
MANIFEST="$BOARD_DIR/totem_appliance_manifest.json"
LOCAL_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || printf unknown)"
LOCAL_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || printf unknown)"
LOCAL_DIRTY_COUNT="$(git -C "$REPO_ROOT" status --short 2>/dev/null | wc -l | tr -d ' ')"

ssh_board() {
  ssh -o ConnectTimeout=10 -o NumberOfPasswordPrompts=1 "$HOST" "$@"
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
}

copy_repo_subset() {
  ssh_board "rm -rf '$REMOTE_REPO' '$REMOTE_OUT_DIR' && mkdir -p '$REMOTE_REPO' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_ROOT' '$REMOTE_REPO' '$REMOTE_OUT_DIR'"
  tar -C "$REPO_ROOT" -czf - scripts/board scripts/remote docs/product/02_ROADMAP_IMPLEMENTACAO_PRODUTO.md docs/product/85_REPRODUTIBILIDADE_PLACA_PARA_IMAGEM.md \
    | ssh_board "tar -C '$REMOTE_REPO' -xzf -"
  ssh_board "printf '%s\n' '$LOCAL_HEAD' > '$REMOTE_REPO/.orange_pi_totem_head' && printf '%s\n' '$LOCAL_BRANCH' > '$REMOTE_REPO/.orange_pi_totem_branch' && printf '%s\n' '$LOCAL_DIRTY_COUNT' > '$REMOTE_REPO/.orange_pi_totem_dirty_entries' && chmod 600 '$REMOTE_REPO/.orange_pi_totem_head' '$REMOTE_REPO/.orange_pi_totem_branch' '$REMOTE_REPO/.orange_pi_totem_dirty_entries'"
}

remote_prepare_checks() {
  ssh_board "REMOTE_REPO='$REMOTE_REPO' bash -s" <<'REMOTE'
set -euo pipefail
cd "$REMOTE_REPO"
bash -n scripts/board/install_totem_appliance.sh
bash -n scripts/board/verify_totem_appliance.sh
bash -n scripts/remote/run_c10_8_installer_idempotent.sh
python3 -m json.tool scripts/board/totem_appliance_manifest.json >/dev/null
scripts/board/verify_totem_appliance.sh --self-test
python3 scripts/board/totem_settings_trigger.py --self-test
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
REMOTE
}

pull_remote_artifacts() {
  mkdir -p "$LOCAL_OUT_DIR/remote"
  chmod 700 "$LOCAL_OUT_DIR/remote"
  scp -q -r "$HOST:$REMOTE_OUT_DIR/." "$LOCAL_OUT_DIR/remote/" || true
}

write_runner_summary() {
  local result="$1"
  cat > "$LOCAL_OUT_DIR/README.md" <<EOF
# C10.8 remote runner artifact

- mode: \`$MODE\`
- result: \`$result\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- source_dirty_entries: \`$LOCAL_DIRTY_COUNT\`
- host: \`<host>\`
- remote_workspace: \`/tmp/dadooh-c10-8-installer-idempotent/...\`
- secrets_published: \`false\`
- config_content_read: \`false\`
- writer_called: \`false\`
- network_changed: \`false\`
- packages_installed: \`false\`
- reboot_called: \`false\`

Artifacts copied from the board are under \`remote/\` and are expected to be
sanitized JSON/text only.
EOF
  chmod 600 "$LOCAL_OUT_DIR/README.md"
}

run_prepare_only() {
  prepare_local
  copy_repo_subset
  remote_prepare_checks
  write_runner_summary "prepare-only-ok"
  printf 'prepare_only_artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_installer_mode() {
  local installer_mode="$1"
  local name="$2"
  prepare_local
  copy_repo_subset
  remote_prepare_checks
  ssh_board "cd '$REMOTE_REPO' && scripts/board/install_totem_appliance.sh '$installer_mode' --repo-root '$REMOTE_REPO' --out-dir '$REMOTE_OUT_DIR/$name'"
  pull_remote_artifacts
  write_runner_summary "$name-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_apply_refresh() {
  echo
  echo "This can alter the dev board appliance layer from the repo copy."
  echo "It still does not install packages, call writer, alter Wi-Fi, reboot, or restart product services by default."
  echo "Type exactly:"
  echo "$APPLY_CONFIRM_PHRASE"
  printf '> '
  IFS= read -r typed
  if [ "$typed" != "$APPLY_CONFIRM_PHRASE" ]; then
    echo "confirmation_mismatch" >&2
    exit 20
  fi
  run_installer_mode "--apply" "apply-dev-refresh"
}

case "$MODE" in
  prepare-only)
    run_prepare_only
    ;;
  dry-run-dev)
    run_installer_mode "--dry-run" "dry-run-dev"
    ;;
  verify-dev)
    run_installer_mode "--verify" "verify-dev"
    ;;
  idempotence-dev-dry-run)
    run_installer_mode "--idempotence-check" "idempotence-dev-dry-run"
    ;;
  apply-dev-refresh)
    run_apply_refresh
    ;;
esac
