#!/usr/bin/env bash
# C14.1.1 - Publish a kiosky-player release package to GitHub Releases.
#
# Inputs:
#   --release-dir <path>   directory containing tar.gz + manifest (from builder)
#   --repo <owner/repo>    GitHub repo (default dadoohai/kiosky-player)
#   --tag <tag>            explicit release tag; default: derived from manifest version
#   --title <title>        release title; default: derived from manifest
#   --prerelease           mark release as prerelease (default ON for channel != stable)
#   --no-prerelease        force non-prerelease
#   --draft                create as draft (does not publish)
#   --prepare-only         show what would be published, do not call gh
#   --publish              publish (default)
#
# Behavior:
#   - never uses --clobber
#   - never deletes existing release
#   - fails fast if gh is not authenticated
#   - never embeds, prints, or persists tokens
#
# Outcomes:
#   GITHUB_CLI_NOT_AUTHENTICATED  -> abort with explicit blocker line
#   release_tag, release_url      -> printed on success
set -euo pipefail

REPO="${REPO:-dadoohai/kiosky-player}"
RELEASE_DIR=""
TAG_OVERRIDE=""
TITLE_OVERRIDE=""
PRERELEASE=""   # tri-state: "", "yes", "no"
DRAFT=0
MODE="publish"

while [[ $# -gt 0 ]]; do
  arg="$1"
  case "$arg" in
    --release-dir=*) RELEASE_DIR="${arg#*=}" ;;
    --release-dir)    shift; RELEASE_DIR="${1:-}" ;;
    --repo=*)         REPO="${arg#*=}" ;;
    --repo)           shift; REPO="${1:-}" ;;
    --tag=*)          TAG_OVERRIDE="${arg#*=}" ;;
    --tag)            shift; TAG_OVERRIDE="${1:-}" ;;
    --title=*)        TITLE_OVERRIDE="${arg#*=}" ;;
    --title)          shift; TITLE_OVERRIDE="${1:-}" ;;
    --prerelease)     PRERELEASE="yes" ;;
    --no-prerelease)  PRERELEASE="no" ;;
    --draft)          DRAFT=1 ;;
    --prepare-only)   MODE="prepare-only" ;;
    --publish)        MODE="publish" ;;
    -h|--help)
      sed -n '2,22p' "$0"
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

log() { printf '[publish_kiosky_player_github_release] %s\n' "$*"; }
die() { printf '[publish_kiosky_player_github_release] FATAL: %s\n' "$*" >&2; exit 1; }

# ----- validate inputs -----
[[ -n "$RELEASE_DIR" ]] || die "missing --release-dir"
[[ -d "$RELEASE_DIR" ]] || die "release dir not found: $RELEASE_DIR"

shopt -s nullglob
MANIFESTS=( "$RELEASE_DIR"/dadooh-kiosky-player-*.manifest.json )
PAYLOADS=( "$RELEASE_DIR"/dadooh-kiosky-player-*.tar.gz )
shopt -u nullglob

(( ${#MANIFESTS[@]} == 1 )) || die "expected exactly 1 manifest in $RELEASE_DIR, found ${#MANIFESTS[@]}"
(( ${#PAYLOADS[@]}  == 1 )) || die "expected exactly 1 payload in $RELEASE_DIR, found ${#PAYLOADS[@]}"

MANIFEST="${MANIFESTS[0]}"
PAYLOAD="${PAYLOADS[0]}"

# ----- parse manifest -----
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

[[ "$(basename "$PAYLOAD")" == "$PAYLOAD_BASENAME" ]] \
  || die "payload basename mismatch: $(basename "$PAYLOAD") != $PAYLOAD_BASENAME"

# re-verify payload sha256 (defense in depth)
ACTUAL_SHA="$(sha256sum "$PAYLOAD" | awk '{print $1}')"
[[ "$ACTUAL_SHA" == "$MANIFEST_SHA" ]] \
  || die "payload sha256 mismatch: actual=$ACTUAL_SHA manifest=$MANIFEST_SHA"

# ----- compute tag / title / prerelease policy -----
if [[ -n "$TAG_OVERRIDE" ]]; then
  TAG="$TAG_OVERRIDE"
else
  TAG="totem-app-${VERSION}"
fi

# tag safety: no spaces, no slashes, plain
[[ "$TAG" =~ ^[A-Za-z0-9._-]+$ ]] || die "unsafe tag: $TAG"

TITLE="${TITLE_OVERRIDE:-Totem app (${COMPONENT}) ${VERSION}}"

if [[ -z "$PRERELEASE" ]]; then
  if [[ "$CHANNEL" == "stable" ]]; then
    PRERELEASE="no"
  else
    PRERELEASE="yes"
  fi
fi

# ----- gh CLI checks -----
command -v gh >/dev/null 2>&1 || { echo "GITHUB_CLI_NOT_AUTHENTICATED" >&2; die "gh CLI not installed"; }

# Auth status: must succeed
if ! gh auth status >/dev/null 2>&1; then
  echo "GITHUB_CLI_NOT_AUTHENTICATED" >&2
  die "gh auth status failed; not publishing"
fi

# ----- abort if release tag already exists (no --clobber, no delete) -----
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  die "release with tag '$TAG' already exists on $REPO (will not clobber)"
fi

log "repo            = $REPO"
log "tag             = $TAG"
log "title           = $TITLE"
log "prerelease      = $PRERELEASE"
log "draft           = $DRAFT"
log "manifest        = $MANIFEST"
log "payload         = $PAYLOAD"
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

# ----- compose release notes -----
NOTES_FILE="$(mktemp -t totem-release-notes-XXXXXX.md)"
trap 'rm -f "$NOTES_FILE"' EXIT

{
  echo "# Dadooh Totem app update — ${COMPONENT} ${VERSION}"
  echo
  echo "Channel: \`${CHANNEL}\`"
  echo "Component: \`${COMPONENT}\`"
  echo "Source commit: \`$(read_json "$MANIFEST" source_commit)\`"
  echo "Source branch: \`$(read_json "$MANIFEST" source_branch)\`"
  echo "Payload SHA256: \`${MANIFEST_SHA}\`"
  echo
  echo "## Assets"
  echo "- \`$(basename "$MANIFEST")\` — manifest (schema dadooh.totem.update.v1)"
  echo "- \`$(basename "$PAYLOAD")\` — kiosky-player tarball"
  echo
  echo "## Apply on device (homologation lab)"
  echo
  echo "\`\`\`"
  echo "/opt/totem/bin/totem-updatectl apply-github-latest --repo ${REPO}"
  echo "\`\`\`"
  echo
  echo "Pre-deploy MVP per C14.1.1. App update only; no OS / kernel / U-Boot changes."
} > "$NOTES_FILE"

# ----- publish -----
GH_ARGS=(
  release create "$TAG"
  --repo "$REPO"
  --title "$TITLE"
  --notes-file "$NOTES_FILE"
)
[[ "$PRERELEASE" == "yes" ]] && GH_ARGS+=( --prerelease )
[[ "$DRAFT"      -eq 1     ]] && GH_ARGS+=( --draft )

log "calling: gh ${GH_ARGS[*]} -- <manifest> <payload>"

RELEASE_URL="$(gh "${GH_ARGS[@]}" -- "$MANIFEST" "$PAYLOAD")"
log "release_url=${RELEASE_URL}"
log "release_tag=${TAG}"
log "published=true"
