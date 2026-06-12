#!/usr/bin/env bash
# C17.5 - Build totem-core release package for GitHub Releases pull deploy.
#
# Outputs in OUT_BASE/<VERSION>/:
#   dadooh-totem-core-<VERSION>.tar.gz
#   dadooh-totem-core-<VERSION>.manifest.json
#
# Payload contains only updater-safe appliance core scripts under bin/.
# It does not include secrets, config, logs, media, NetworkManager profiles,
# systemd units, kernel/BSP artifacts, player launchers, or the updater as a
# self-update.
#
# Stable builds are production-gated. They require ALLOW_C18_STABLE_PROMOTION=1
# plus --stable-promotion-evidence and artifact paths for release gate,
# server-side evidence, server-side trusted key, server-side trust anchor, soak,
# power-loss matrix, operator thaw decision, and expected image identity.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/builder/totem-os/orange_pi_totem}"
COMPONENT="totem-core"
CHANNEL="${CHANNEL:-homologation}"
OUT_BASE="${OUT_BASE:-releases/core-updates}"
SOURCE_REPO_FULL="${SOURCE_REPO_FULL:-dadoohai/orange_pi_totem}"
REQUIRED_BASE_IMAGE_MIN="${REQUIRED_BASE_IMAGE_MIN:-c17.4.2}"
REQUIRED_DEVICE_TRACK="${REQUIRED_DEVICE_TRACK:-c18-hwdecode}"
STABLE_PROMOTION_EVIDENCE="${STABLE_PROMOTION_EVIDENCE:-}"
STABLE_RELEASE_GATE_SUMMARY="${STABLE_RELEASE_GATE_SUMMARY:-}"
STABLE_SERVER_SIDE_EVIDENCE="${STABLE_SERVER_SIDE_EVIDENCE:-}"
STABLE_SERVER_SIDE_TRUST_ANCHOR_EVIDENCE="${STABLE_SERVER_SIDE_TRUST_ANCHOR_EVIDENCE:-}"
STABLE_SOAK_SUMMARY="${STABLE_SOAK_SUMMARY:-}"
STABLE_OPERATOR_THAW_DECISION="${STABLE_OPERATOR_THAW_DECISION:-}"
STABLE_EXPECT_IMAGE_TAG="${STABLE_EXPECT_IMAGE_TAG:-}"
STABLE_EXPECT_IMAGE_SHA256="${STABLE_EXPECT_IMAGE_SHA256:-}"
STABLE_EXPECT_IMAGE_MARKER_SHA256="${STABLE_EXPECT_IMAGE_MARKER_SHA256:-}"
MODE="build-package"
ALLOW_DIRTY=0
VERSION_OVERRIDE="${VERSION:-}"
STABLE_SERVER_SIDE_TRUSTED_KEY_PEMS=()
STABLE_POWERLOSS_EVIDENCE_DIRS=()

CORE_FILES=(
  totem_setup_visual_wizard.py
  totem_wifi_nm_adapter.py
  totem_visual_splash.py
  totem_status_aggregate.py
  totem_status_render_preview.py
  totem_config_contract_validate.py
  totem_open_settings_session.sh
  totem_visual_tty_guard.sh
  totem_firstboot_gate.sh
  totem_status_renderer.sh
  totem_settings_trigger.py
  totem_open_settings_cleanup.sh
  totem_visual_setup_writer_handoff.py
  totem_config_writer_real.py
  totem_setup_minimal_server.py
  totem_setup_local_wizard.py
)

for arg in "$@"; do
  case "$arg" in
    --prepare-only) MODE="prepare-only" ;;
    --build-package) MODE="build-package" ;;
    --allow-dirty) ALLOW_DIRTY=1 ;;
    --version=*) VERSION_OVERRIDE="${arg#*=}" ;;
    --repo-root=*) REPO_ROOT="${arg#*=}" ;;
    --out-base=*) OUT_BASE="${arg#*=}" ;;
    --channel=*) CHANNEL="${arg#*=}" ;;
    --stable-promotion-evidence=*) STABLE_PROMOTION_EVIDENCE="${arg#*=}" ;;
    --stable-release-gate-summary=*) STABLE_RELEASE_GATE_SUMMARY="${arg#*=}" ;;
    --stable-server-side-evidence=*) STABLE_SERVER_SIDE_EVIDENCE="${arg#*=}" ;;
    --stable-server-side-trusted-key-pem=*) STABLE_SERVER_SIDE_TRUSTED_KEY_PEMS+=( "${arg#*=}" ) ;;
    --stable-server-side-trust-anchor-evidence=*) STABLE_SERVER_SIDE_TRUST_ANCHOR_EVIDENCE="${arg#*=}" ;;
    --stable-soak-summary=*) STABLE_SOAK_SUMMARY="${arg#*=}" ;;
    --stable-powerloss-evidence-dir=*) STABLE_POWERLOSS_EVIDENCE_DIRS+=( "${arg#*=}" ) ;;
    --stable-operator-thaw-decision=*) STABLE_OPERATOR_THAW_DECISION="${arg#*=}" ;;
    --stable-expect-image-tag=*) STABLE_EXPECT_IMAGE_TAG="${arg#*=}" ;;
    --stable-expect-image-sha256=*) STABLE_EXPECT_IMAGE_SHA256="${arg#*=}" ;;
    --stable-expect-image-marker-sha256=*) STABLE_EXPECT_IMAGE_MARKER_SHA256="${arg#*=}" ;;
    -h|--help)
      sed -n '2,21p' "$0"
      exit 0
      ;;
    *)
      echo "FATAL: unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

log() { printf '[build_totem_core_release_package] %s\n' "$*"; }
die() { printf '[build_totem_core_release_package] FATAL: %s\n' "$*" >&2; exit 1; }

git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || die "REPO_ROOT ($REPO_ROOT) is not a git repo"
for file in "${CORE_FILES[@]}"; do
  [[ -f "$REPO_ROOT/scripts/board/$file" ]] || die "missing core file: scripts/board/$file"
done

pushd "$REPO_ROOT" >/dev/null
SOURCE_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
SOURCE_COMMIT="$(git rev-parse HEAD)"
SOURCE_COMMIT_SHORT="$(git rev-parse --short=7 HEAD)"
SOURCE_COMMIT_EPOCH="$(git show -s --format=%ct HEAD)"
DIRTY=0
if ! git diff --quiet || ! git diff --cached --quiet; then
  DIRTY=1
fi
popd >/dev/null

if [[ "$DIRTY" -eq 1 && "$ALLOW_DIRTY" -eq 0 ]]; then
  die "orange_pi_totem working tree is dirty (use --allow-dirty to override)"
fi

if [[ -z "$VERSION_OVERRIDE" ]]; then
  VERSION="c17.5-core-mvp-$(date -u +%Y%m%d-%H%M%S)-${SOURCE_COMMIT_SHORT}"
else
  VERSION="$VERSION_OVERRIDE"
fi

if ! [[ "$VERSION" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
  die "version contains unsafe characters: $VERSION"
fi
if [[ "$VERSION" == *..* ]]; then
  die "version contains unsafe characters: $VERSION"
fi

if ! [[ "$CHANNEL" =~ ^(lab|homologation|stable)$ ]]; then
  die "unsupported channel: $CHANNEL (expected lab, homologation, or stable)"
fi

STABLE_PROMOTION_EVIDENCE_SHA256=""
if [[ "$CHANNEL" == "stable" ]]; then
  [[ "${ALLOW_C18_STABLE_PROMOTION:-0}" == "1" ]] \
    || die "stable channel is locked until explicit production promotion (set ALLOW_C18_STABLE_PROMOTION=1 and provide --stable-promotion-evidence)"
  [[ -n "$STABLE_PROMOTION_EVIDENCE" && -f "$STABLE_PROMOTION_EVIDENCE" ]] \
    || die "stable channel requires --stable-promotion-evidence=<json>"
  [[ -n "$STABLE_RELEASE_GATE_SUMMARY" && -f "$STABLE_RELEASE_GATE_SUMMARY" ]] \
    || die "stable channel requires --stable-release-gate-summary=<json>"
  [[ -n "$STABLE_SERVER_SIDE_EVIDENCE" && -f "$STABLE_SERVER_SIDE_EVIDENCE" ]] \
    || die "stable channel requires --stable-server-side-evidence=<json>"
  (( ${#STABLE_SERVER_SIDE_TRUSTED_KEY_PEMS[@]} > 0 )) \
    || die "stable channel requires at least one --stable-server-side-trusted-key-pem=<pem>"
  [[ -n "$STABLE_SERVER_SIDE_TRUST_ANCHOR_EVIDENCE" && -f "$STABLE_SERVER_SIDE_TRUST_ANCHOR_EVIDENCE" ]] \
    || die "stable channel requires --stable-server-side-trust-anchor-evidence=<json>"
  [[ -n "$STABLE_SOAK_SUMMARY" && -f "$STABLE_SOAK_SUMMARY" ]] \
    || die "stable channel requires --stable-soak-summary=<json>"
  [[ -n "$STABLE_OPERATOR_THAW_DECISION" && -f "$STABLE_OPERATOR_THAW_DECISION" ]] \
    || die "stable channel requires --stable-operator-thaw-decision=<json>"
  [[ -n "$STABLE_EXPECT_IMAGE_TAG" ]] || die "stable channel requires --stable-expect-image-tag"
  [[ -n "$STABLE_EXPECT_IMAGE_SHA256" ]] || die "stable channel requires --stable-expect-image-sha256"
  [[ -n "$STABLE_EXPECT_IMAGE_MARKER_SHA256" ]] || die "stable channel requires --stable-expect-image-marker-sha256"
  (( ${#STABLE_POWERLOSS_EVIDENCE_DIRS[@]} > 0 )) \
    || die "stable channel requires at least one --stable-powerloss-evidence-dir=<dir>"
  STABLE_GATE_CMD=(
    python3 "$REPO_ROOT/scripts/qa/c18_stable_promotion_gate.py"
    --evidence "$STABLE_PROMOTION_EVIDENCE" \
    --release-gate-summary "$STABLE_RELEASE_GATE_SUMMARY" \
    --server-side-evidence "$STABLE_SERVER_SIDE_EVIDENCE" \
    --server-side-trust-anchor-evidence "$STABLE_SERVER_SIDE_TRUST_ANCHOR_EVIDENCE" \
    --soak-summary "$STABLE_SOAK_SUMMARY" \
    --operator-thaw-decision "$STABLE_OPERATOR_THAW_DECISION" \
    --expect-image-tag "$STABLE_EXPECT_IMAGE_TAG" \
    --expect-image-sha256 "$STABLE_EXPECT_IMAGE_SHA256" \
    --expect-image-marker-sha256 "$STABLE_EXPECT_IMAGE_MARKER_SHA256" \
    --json
  )
  for run_dir in "${STABLE_POWERLOSS_EVIDENCE_DIRS[@]}"; do
    [[ -d "$run_dir" ]] || die "stable powerloss evidence dir not found: $run_dir"
    STABLE_GATE_CMD+=( --powerloss-evidence-dir "$run_dir" )
  done
  for key_pem in "${STABLE_SERVER_SIDE_TRUSTED_KEY_PEMS[@]}"; do
    [[ -f "$key_pem" ]] || die "stable server-side trusted key not found: $key_pem"
    STABLE_GATE_CMD+=( --server-side-trusted-key-pem "$key_pem" )
  done
  if ! "${STABLE_GATE_CMD[@]}" >/dev/null
  then
    die "stable promotion evidence failed scripts/qa/c18_stable_promotion_gate.py"
  fi
  STABLE_PROMOTION_EVIDENCE_SHA256="$(sha256sum "$STABLE_PROMOTION_EVIDENCE" | awk '{print $1}')"
fi

OUT_DIR="${OUT_BASE}/${VERSION}"
PAYLOAD_NAME="dadooh-${COMPONENT}-${VERSION}.tar.gz"
MANIFEST_NAME="dadooh-${COMPONENT}-${VERSION}.manifest.json"
PAYLOAD_PATH="${OUT_DIR}/${PAYLOAD_NAME}"
MANIFEST_PATH="${OUT_DIR}/${MANIFEST_NAME}"

log "component       = $COMPONENT"
log "version         = $VERSION"
log "channel         = $CHANNEL"
log "source_repo     = $SOURCE_REPO_FULL"
log "source_branch   = $SOURCE_BRANCH"
log "source_commit   = $SOURCE_COMMIT"
log "device_track    = $REQUIRED_DEVICE_TRACK"
if [[ "$CHANNEL" == "stable" ]]; then
  log "stable_evidence = $STABLE_PROMOTION_EVIDENCE"
fi
log "dirty           = $DIRTY"
log "out_dir         = $OUT_DIR"
log "mode            = $MODE"

if [[ "$MODE" == "prepare-only" ]]; then
  log "prepare_only=true"
  log "would_build_payload=${PAYLOAD_PATH}"
  log "would_build_manifest=${MANIFEST_PATH}"
  exit 0
fi

STAGE_DIR="$(mktemp -d -t totem-core-stage-XXXXXX)"
SCAN_HITS_FILE="$(mktemp)"
cleanup() { rm -rf "$STAGE_DIR" "$SCAN_HITS_FILE"; }
trap cleanup EXIT

mkdir -p "$STAGE_DIR/bin" "$STAGE_DIR/health" "$STAGE_DIR/manifest-fragment"
for file in "${CORE_FILES[@]}"; do
  install -m 0755 "$REPO_ROOT/scripts/board/$file" "$STAGE_DIR/bin/$file"
done

cat > "$STAGE_DIR/health/totem-core-health.json" <<JSON
{
  "schema": "dadooh.totem.core.health.v1",
  "component": "totem-core",
  "self_tests": [
    "python3 bin/totem_setup_visual_wizard.py --self-test",
    "python3 bin/totem_wifi_nm_adapter.py --self-test",
    "python3 bin/totem_visual_splash.py --self-test",
    "python3 bin/totem_status_render_preview.py --self-test",
    "python3 bin/totem_config_contract_validate.py --self-test",
    "bash -n bin/totem_open_settings_session.sh",
    "bash -n bin/totem_visual_tty_guard.sh",
    "bash -n bin/totem_firstboot_gate.sh",
    "bash -n bin/totem_status_renderer.sh",
    "restore-order-static-check"
  ]
}
JSON

cat > "$STAGE_DIR/manifest-fragment/totem-core.json" <<JSON
{
  "component": "totem-core",
  "layout": "/data/core/totem",
  "fallback": "/opt/totem/core-fallback/bin",
  "wrappers": "/opt/totem/bin",
  "systemd_units_included": false,
  "updater_self_update": false
}
JSON

FORBIDDEN_NAMES=(
  ".git"
  "__pycache__"
  ".pytest_cache"
  ".venv"
  "config.json"
  "private-values.seed.json"
  ".env"
  "credentials.json"
  "id_rsa"
  "id_ed25519"
)
for fname in "${FORBIDDEN_NAMES[@]}"; do
  if find "$STAGE_DIR" -name "$fname" -print -quit | grep -q .; then
    die "forbidden entry present in staged tree: $fname"
  fi
done

SCAN_PATTERNS=(
  '-----BEGIN [A-Z ]+PRIVATE KEY-----'
  'AKIA[0-9A-Z]{16}'
  'ghp_[A-Za-z0-9]{30,}'
  'gho_[A-Za-z0-9]{30,}'
  'ghs_[A-Za-z0-9]{30,}'
  'github_pat_[A-Za-z0-9_]{30,}'
)
SCAN_REGEX="$(IFS='|'; echo "${SCAN_PATTERNS[*]}")"
if grep -rEl --binary-files=without-match "$SCAN_REGEX" "$STAGE_DIR" > "$SCAN_HITS_FILE" 2>/dev/null; then
  if [[ -s "$SCAN_HITS_FILE" ]]; then
    log "secret scan hits (paths only, content NOT printed):"
    sed "s|^${STAGE_DIR}/||" "$SCAN_HITS_FILE" >&2
    die "secret-like content found in staged tree; aborting"
  fi
fi

mkdir -p "$OUT_DIR"
if [[ "$CHANNEL" == "stable" ]]; then
  cp -f "$STABLE_PROMOTION_EVIDENCE" "$OUT_DIR/c18-stable-promotion-evidence.json"
fi
tar \
  --owner=0 --group=0 --numeric-owner \
  --sort=name \
  --mtime="@${SOURCE_COMMIT_EPOCH}" \
  -czf "$PAYLOAD_PATH" \
  -C "$STAGE_DIR" .

PAYLOAD_BYTES="$(stat -c '%s' "$PAYLOAD_PATH")"
PAYLOAD_SHA256="$(sha256sum "$PAYLOAD_PATH" | awk '{print $1}')"
NOW_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 - "$MANIFEST_PATH" <<PY
import json, sys
manifest = {
    "schema": "dadooh.totem.update.v1",
    "component": "${COMPONENT}",
    "version": "${VERSION}",
    "channel": "${CHANNEL}",
    "source_repo": "${SOURCE_REPO_FULL}",
    "source_branch": "${SOURCE_BRANCH}",
    "source_commit": "${SOURCE_COMMIT}",
    "source_dirty": bool(${DIRTY}),
    "stable_promotion_evidence_sha256": "${STABLE_PROMOTION_EVIDENCE_SHA256}",
    "payload": "${PAYLOAD_NAME}",
    "payload_sha256": "${PAYLOAD_SHA256}",
    "payload_bytes": ${PAYLOAD_BYTES},
    "entrypoint": "bin/totem_setup_visual_wizard.py",
    "required_base_image_min": "${REQUIRED_BASE_IMAGE_MIN}",
    "requires": {
        "device": "orangepizero3",
        "base_image_min": "${REQUIRED_BASE_IMAGE_MIN}",
        "device_track": "${REQUIRED_DEVICE_TRACK}",
        "updater_features": [
            "c18-freeze-kiosky-player-v1",
            "c18-rollback-reapply-v1",
            "c18-safe-payload-v1",
            "c18-track-v1"
        ]
    },
    "updates": [
        "wizard",
        "splash",
        "status",
        "settings-session",
        "wifi-adapter",
        "config-contract",
        "firstboot"
    ],
    "health_checks": [
        "wizard_self_test",
        "wifi_adapter_self_test",
        "splash_self_test",
        "status_preview_self_test",
        "config_contract_self_test",
        "bash_syntax",
        "restore_order_static"
    ],
    "created_at": "${NOW_UTC}",
    "created_at_utc": "${NOW_UTC}"
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, sort_keys=True)
    f.write("\\n")
PY

python3 -m json.tool "$MANIFEST_PATH" >/dev/null || die "manifest JSON failed to validate"

log "build_package=true"
log "payload_path=${PAYLOAD_PATH}"
log "manifest_path=${MANIFEST_PATH}"
log "payload_sha256=${PAYLOAD_SHA256}"
log "payload_bytes=${PAYLOAD_BYTES}"
log "source_commit=${SOURCE_COMMIT}"
log "version=${VERSION}"
