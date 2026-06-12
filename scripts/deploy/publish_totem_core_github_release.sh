#!/usr/bin/env bash
# C17.5 - Publish a totem-core release package to GitHub Releases.
#
# Uses gh on the builder only. Never prints or persists tokens.

set -euo pipefail

REPO="${REPO:-dadoohai/orange_pi_totem}"
RELEASE_DIR=""
TAG_OVERRIDE=""
TITLE_OVERRIDE=""
PRERELEASE=""
BASE_REF="${C18_OTA_BASE_REF:-}"
DRAFT=0
MODE="publish"

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
  if ! python3 "$REPO_ROOT/scripts/qa/c18_stable_promotion_gate.py" \
    --evidence "$STABLE_EVIDENCE" \
    --json >/dev/null
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
  ASSETS+=( "$STABLE_EVIDENCE" )
fi
log "calling: gh ${GH_ARGS[*]} -- <manifest> <payload> <gate_evidence>"
RELEASE_URL="$(gh "${GH_ARGS[@]}" -- "${ASSETS[@]}")"
log "release_url=${RELEASE_URL}"
log "release_tag=${TAG}"
log "published=true"
