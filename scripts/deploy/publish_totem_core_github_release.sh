#!/usr/bin/env bash
# C17.5 - Publish a totem-core release package to GitHub Releases.
#
# Uses gh on the builder only. Never prints or persists tokens.
#
# Stable publishes are production-gated. They require
# ALLOW_C18_STABLE_PROMOTION=1 plus artifact paths for release gate,
# server-side evidence, server-side trusted key, server-side trust anchor, soak,
# power-loss matrix, operator thaw decision, and expected image identity.

set -euo pipefail

REPO="${REPO:-dadoohai/orange_pi_totem}"
RELEASE_DIR=""
TAG_OVERRIDE=""
TITLE_OVERRIDE=""
PRERELEASE=""
BASE_REF="${C18_OTA_BASE_REF:-}"
DRAFT=0
MODE="publish"
STABLE_RELEASE_GATE_SUMMARY=""
STABLE_SERVER_SIDE_EVIDENCE=""
STABLE_SERVER_SIDE_TRUST_ANCHOR_EVIDENCE=""
STABLE_SOAK_SUMMARY=""
STABLE_OPERATOR_THAW_DECISION=""
STABLE_EXPECT_IMAGE_TAG=""
STABLE_EXPECT_IMAGE_SHA256=""
STABLE_EXPECT_IMAGE_MARKER_SHA256=""
STABLE_RELEASE_GATE_SUMMARY_SHA=""
STABLE_SERVER_SIDE_TRUSTED_KEY_PEMS=()
STABLE_POWERLOSS_EVIDENCE_DIRS=()
STABLE_SERVER_SIDE_ASSETS=()

while [[ $# -gt 0 ]]; do
  arg="$1"
  case "$arg" in
    --release-dir=*) RELEASE_DIR="${arg#*=}" ;;
    --release-dir) shift; RELEASE_DIR="${1:-}" ;;
    --repo=*) REPO="${arg#*=}" ;;
    --repo) shift; REPO="${1:-}" ;;
    --tag=*) TAG_OVERRIDE="${arg#*=}" ;;
    --tag) shift; TAG_OVERRIDE="${1:-}" ;;
    --title=*) TITLE_OVERRIDE="${arg#*=}" ;;
    --title) shift; TITLE_OVERRIDE="${1:-}" ;;
    --base-ref=*) BASE_REF="${arg#*=}" ;;
    --base-ref) shift; BASE_REF="${1:-}" ;;
    --stable-release-gate-summary=*) STABLE_RELEASE_GATE_SUMMARY="${arg#*=}" ;;
    --stable-release-gate-summary) shift; STABLE_RELEASE_GATE_SUMMARY="${1:-}" ;;
    --stable-server-side-evidence=*) STABLE_SERVER_SIDE_EVIDENCE="${arg#*=}" ;;
    --stable-server-side-evidence) shift; STABLE_SERVER_SIDE_EVIDENCE="${1:-}" ;;
    --stable-server-side-trusted-key-pem=*) STABLE_SERVER_SIDE_TRUSTED_KEY_PEMS+=( "${arg#*=}" ) ;;
    --stable-server-side-trusted-key-pem) shift; STABLE_SERVER_SIDE_TRUSTED_KEY_PEMS+=( "${1:-}" ) ;;
    --stable-server-side-trust-anchor-evidence=*) STABLE_SERVER_SIDE_TRUST_ANCHOR_EVIDENCE="${arg#*=}" ;;
    --stable-server-side-trust-anchor-evidence) shift; STABLE_SERVER_SIDE_TRUST_ANCHOR_EVIDENCE="${1:-}" ;;
    --stable-soak-summary=*) STABLE_SOAK_SUMMARY="${arg#*=}" ;;
    --stable-soak-summary) shift; STABLE_SOAK_SUMMARY="${1:-}" ;;
    --stable-powerloss-evidence-dir=*) STABLE_POWERLOSS_EVIDENCE_DIRS+=( "${arg#*=}" ) ;;
    --stable-powerloss-evidence-dir) shift; STABLE_POWERLOSS_EVIDENCE_DIRS+=( "${1:-}" ) ;;
    --stable-operator-thaw-decision=*) STABLE_OPERATOR_THAW_DECISION="${arg#*=}" ;;
    --stable-operator-thaw-decision) shift; STABLE_OPERATOR_THAW_DECISION="${1:-}" ;;
    --stable-expect-image-tag=*) STABLE_EXPECT_IMAGE_TAG="${arg#*=}" ;;
    --stable-expect-image-tag) shift; STABLE_EXPECT_IMAGE_TAG="${1:-}" ;;
    --stable-expect-image-sha256=*) STABLE_EXPECT_IMAGE_SHA256="${arg#*=}" ;;
    --stable-expect-image-sha256) shift; STABLE_EXPECT_IMAGE_SHA256="${1:-}" ;;
    --stable-expect-image-marker-sha256=*) STABLE_EXPECT_IMAGE_MARKER_SHA256="${arg#*=}" ;;
    --stable-expect-image-marker-sha256) shift; STABLE_EXPECT_IMAGE_MARKER_SHA256="${1:-}" ;;
    --prerelease) PRERELEASE="yes" ;;
    --no-prerelease) PRERELEASE="no" ;;
    --draft) DRAFT=1 ;;
    --prepare-only) MODE="prepare-only" ;;
    --publish) MODE="publish" ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *)
      if [[ -z "$RELEASE_DIR" && -d "$arg" ]]; then
        RELEASE_DIR="$arg"
      else
        echo "FATAL: unknown arg: $arg" >&2
        exit 2
      fi
      ;;
  esac
  shift
done

log() { printf '[publish_totem_core_github_release] %s\n' "$*"; }
die() { printf '[publish_totem_core_github_release] FATAL: %s\n' "$*" >&2; exit 1; }

[[ -n "$RELEASE_DIR" ]] || die "missing --release-dir"
[[ -d "$RELEASE_DIR" ]] || die "release dir not found: $RELEASE_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

shopt -s nullglob
MANIFESTS=( "$RELEASE_DIR"/dadooh-totem-core-*.manifest.json )
PAYLOADS=( "$RELEASE_DIR"/dadooh-totem-core-*.tar.gz )
shopt -u nullglob

(( ${#MANIFESTS[@]} == 1 )) || die "expected exactly 1 manifest in $RELEASE_DIR, found ${#MANIFESTS[@]}"
(( ${#PAYLOADS[@]} == 1 )) || die "expected exactly 1 payload in $RELEASE_DIR, found ${#PAYLOADS[@]}"

MANIFEST="${MANIFESTS[0]}"
PAYLOAD="${PAYLOADS[0]}"

read_json() {
  python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
key = sys.argv[2]
val = d
for part in key.split('.'):
    val = val[part]
print(val)
" "$1" "$2"
}

append_unique_asset() {
  local candidate="$1"
  local existing
  for existing in "${ASSETS[@]}"; do
    [[ "$existing" == "$candidate" ]] && return 0
  done
  ASSETS+=( "$candidate" )
}

VERSION="$(read_json "$MANIFEST" version)"
CHANNEL="$(read_json "$MANIFEST" channel)"
COMPONENT="$(read_json "$MANIFEST" component)"
MANIFEST_SHA="$(read_json "$MANIFEST" payload_sha256)"
PAYLOAD_BASENAME="$(read_json "$MANIFEST" payload)"
SOURCE_COMMIT="$(read_json "$MANIFEST" source_commit)"
GATE_EVIDENCE="$RELEASE_DIR/c18-ota-release-gate.json"
STABLE_EVIDENCE="$RELEASE_DIR/c18-stable-promotion-evidence.json"

[[ "$COMPONENT" == "totem-core" ]] || die "manifest component is not totem-core"
[[ "$(basename "$PAYLOAD")" == "$PAYLOAD_BASENAME" ]] \
  || die "payload basename mismatch: $(basename "$PAYLOAD") != $PAYLOAD_BASENAME"
[[ "$SOURCE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "manifest source_commit is not a full SHA: $SOURCE_COMMIT"
if [[ "$CHANNEL" == "stable" ]]; then
  STABLE_EVIDENCE_SHA="$(read_json "$MANIFEST" stable_promotion_evidence_sha256)"
  [[ "${ALLOW_C18_STABLE_PROMOTION:-0}" == "1" ]] \
    || die "stable channel is locked until explicit production promotion (set ALLOW_C18_STABLE_PROMOTION=1)"
  [[ -f "$STABLE_EVIDENCE" ]] \
    || die "stable channel requires $STABLE_EVIDENCE"
  [[ -n "$STABLE_RELEASE_GATE_SUMMARY" && -f "$STABLE_RELEASE_GATE_SUMMARY" ]] \
    || die "stable channel requires --stable-release-gate-summary=<json>"
  STABLE_RELEASE_GATE_SUMMARY_SHA="$(sha256sum "$STABLE_RELEASE_GATE_SUMMARY" | awk '{print $1}')"
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
    --evidence "$STABLE_EVIDENCE" \
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
  [[ "$STABLE_EVIDENCE_SHA" =~ ^[0-9a-f]{64}$ ]] \
    || die "stable manifest must include stable_promotion_evidence_sha256"
  ACTUAL_STABLE_EVIDENCE_SHA="$(sha256sum "$STABLE_EVIDENCE" | awk '{print $1}')"
  [[ "$ACTUAL_STABLE_EVIDENCE_SHA" == "$STABLE_EVIDENCE_SHA" ]] \
    || die "stable evidence sha256 mismatch: actual=$ACTUAL_STABLE_EVIDENCE_SHA manifest=$STABLE_EVIDENCE_SHA"
fi

ACTUAL_SHA="$(sha256sum "$PAYLOAD" | awk '{print $1}')"
[[ "$ACTUAL_SHA" == "$MANIFEST_SHA" ]] \
  || die "payload sha256 mismatch: actual=$ACTUAL_SHA manifest=$MANIFEST_SHA"

[[ -n "$REPO_ROOT" && -f "$REPO_ROOT/scripts/qa/c18_ota_release_gate.py" ]] \
  || die "c18 OTA release gate not found; run from orange_pi_totem checkout"
[[ -n "$BASE_REF" ]] \
  || die "missing --base-ref (or C18_OTA_BASE_REF); publish must compare committed diff against an explicit base"
TMP_GATE_EVIDENCE="$(mktemp -t c18-ota-release-gate-XXXXXX.json)"
trap 'rm -f "$TMP_GATE_EVIDENCE"' EXIT
python3 "$REPO_ROOT/scripts/qa/c18_ota_release_gate.py" \
  --package-manifest "$MANIFEST" \
  --package-payload "$PAYLOAD" \
  --base-ref "$BASE_REF" \
  --json >"$TMP_GATE_EVIDENCE" \
  || die "c18 OTA release gate failed; refusing to publish"
mv -f "$TMP_GATE_EVIDENCE" "$GATE_EVIDENCE"
if [[ "$CHANNEL" == "stable" ]]; then
  ACTUAL_GATE_EVIDENCE_SHA="$(sha256sum "$GATE_EVIDENCE" | awk '{print $1}')"
  [[ "$ACTUAL_GATE_EVIDENCE_SHA" == "$STABLE_RELEASE_GATE_SUMMARY_SHA" ]] \
    || die "stable release gate summary sha256 mismatch after generation: actual=$ACTUAL_GATE_EVIDENCE_SHA expected=$STABLE_RELEASE_GATE_SUMMARY_SHA"
  STABLE_SERVER_SIDE_ASSET_LIST="$(
    PYTHONDONTWRITEBYTECODE=1 python3 "$REPO_ROOT/scripts/qa/c18_server_side_publish_asset_collect.py" \
      --server-side-evidence "$STABLE_SERVER_SIDE_EVIDENCE" \
      --trust-anchor-evidence "$STABLE_SERVER_SIDE_TRUST_ANCHOR_EVIDENCE" \
      --expected-release-gate-sha256 "$STABLE_RELEASE_GATE_SUMMARY_SHA"
  )" || die "stable server-side publish assets could not be collected from evidence"
  while IFS= read -r asset; do
    [[ -n "$asset" ]] && STABLE_SERVER_SIDE_ASSETS+=( "$asset" )
  done <<< "$STABLE_SERVER_SIDE_ASSET_LIST"
fi

if [[ -n "$TAG_OVERRIDE" ]]; then
  TAG="$TAG_OVERRIDE"
else
  TAG="totem-core-${VERSION}"
fi
[[ "$TAG" =~ ^[A-Za-z0-9._-]+$ ]] || die "unsafe tag: $TAG"

TITLE="${TITLE_OVERRIDE:-Totem core ${VERSION}}"
if [[ -z "$PRERELEASE" ]]; then
  if [[ "$CHANNEL" == "stable" ]]; then PRERELEASE="no"; else PRERELEASE="yes"; fi
fi

command -v gh >/dev/null 2>&1 || { echo "GITHUB_CLI_NOT_AUTHENTICATED" >&2; die "gh CLI not installed"; }
if ! gh auth status >/dev/null 2>&1; then
  echo "GITHUB_CLI_NOT_AUTHENTICATED" >&2
  die "gh auth status failed; not publishing"
fi
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  die "release with tag '$TAG' already exists on $REPO (will not clobber)"
fi

REMOTE_TAG_TARGET=""
REMOTE_TAG_REFS="$(git ls-remote --tags "https://github.com/${REPO}.git" "refs/tags/${TAG}" "refs/tags/${TAG}^{}" 2>/dev/null || true)"
if [[ -n "$REMOTE_TAG_REFS" ]]; then
  REMOTE_TAG_TARGET="$(printf '%s\n' "$REMOTE_TAG_REFS" | awk -v tag="refs/tags/${TAG}^{}" '$2 == tag {print $1; found=1} END {if (!found) exit 1}' 2>/dev/null || true)"
  if [[ -z "$REMOTE_TAG_TARGET" ]]; then
    REMOTE_TAG_TARGET="$(printf '%s\n' "$REMOTE_TAG_REFS" | awk -v tag="refs/tags/${TAG}" '$2 == tag {print $1; exit}')"
  fi
  [[ "$REMOTE_TAG_TARGET" == "$SOURCE_COMMIT" ]] \
    || die "remote tag '$TAG' does not point to manifest source_commit (tag=$REMOTE_TAG_TARGET source=$SOURCE_COMMIT)"
fi

log "repo            = $REPO"
log "tag             = $TAG"
log "source_commit   = $SOURCE_COMMIT"
if [[ -n "$REMOTE_TAG_REFS" ]]; then
  log "tag_target      = $REMOTE_TAG_TARGET"
else
  log "tag_target      = ${SOURCE_COMMIT} (will be created by gh --target)"
fi
log "title           = $TITLE"
log "prerelease      = $PRERELEASE"
log "draft           = $DRAFT"
log "manifest        = $MANIFEST"
log "payload         = $PAYLOAD"
log "base_ref        = $BASE_REF"
log "gate_evidence   = $GATE_EVIDENCE"
if [[ "$CHANNEL" == "stable" ]]; then
  log "stable_evidence = $STABLE_EVIDENCE"
  log "stable_server_side_evidence = $STABLE_SERVER_SIDE_EVIDENCE"
  log "stable_server_side_trust_anchor = $STABLE_SERVER_SIDE_TRUST_ANCHOR_EVIDENCE"
  log "stable_server_side_assets = ${#STABLE_SERVER_SIDE_ASSETS[@]}"
fi
log "payload_sha256  = $MANIFEST_SHA"
log "version         = $VERSION"
log "channel         = $CHANNEL"
log "mode            = $MODE"

if [[ "$MODE" == "prepare-only" ]]; then
  log "prepare_only=true"
  log "would_publish=true"
  log "release_tag=${TAG}"
  exit 0
fi

NOTES_FILE="$(mktemp -t totem-core-release-notes-XXXXXX.md)"
trap 'rm -f "$NOTES_FILE" "$TMP_GATE_EVIDENCE"' EXIT

{
  echo "# Dadooh Totem core update — ${VERSION}"
  echo
  echo "Channel: \`${CHANNEL}\`"
  echo "Component: \`${COMPONENT}\`"
  echo "Source commit: \`$(read_json "$MANIFEST" source_commit)\`"
  echo "Source branch: \`$(read_json "$MANIFEST" source_branch)\`"
  echo "Payload SHA256: \`${MANIFEST_SHA}\`"
  echo
  echo "Scope: wizard/configurator, splash, status, Wi-Fi adapter and firstboot helpers."
  echo "Out of scope: OS, kernel, U-Boot, DTB, NetworkManager, read-only, updater self-update and player timing."
  echo
  echo "Apply on device:"
  echo
  echo "\`\`\`"
  echo "/opt/totem/bin/totem-updatectl apply-github-latest --component totem-core --repo ${REPO}"
  echo "\`\`\`"
} > "$NOTES_FILE"

GH_ARGS=(
  release create "$TAG"
  --repo "$REPO"
  --title "$TITLE"
  --notes-file "$NOTES_FILE"
)
if [[ -n "$REMOTE_TAG_REFS" ]]; then
  GH_ARGS+=( --verify-tag )
else
  GH_ARGS+=( --target "$SOURCE_COMMIT" )
fi
[[ "$PRERELEASE" == "yes" ]] && GH_ARGS+=( --prerelease )
[[ "$DRAFT" -eq 1 ]] && GH_ARGS+=( --draft )

ASSETS=( "$MANIFEST" "$PAYLOAD" "$GATE_EVIDENCE" )
if [[ "$CHANNEL" == "stable" ]]; then
  append_unique_asset "$STABLE_EVIDENCE"
  for asset in "${STABLE_SERVER_SIDE_ASSETS[@]}"; do
    append_unique_asset "$asset"
  done
fi
log "calling: gh ${GH_ARGS[*]} -- <validated-assets>"
RELEASE_URL="$(gh "${GH_ARGS[@]}" -- "${ASSETS[@]}")"
log "release_url=${RELEASE_URL}"
log "release_tag=${TAG}"
log "published=true"
