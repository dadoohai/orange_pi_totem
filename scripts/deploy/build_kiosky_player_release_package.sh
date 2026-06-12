#!/usr/bin/env bash
# C14.1.1 - Build kiosky-player release package for GitHub Releases pull deploy.
#
# C18 guardrail: this is a historical packaging helper, not the current C18
# OTA path. Release eligibility, channel policy, hardware validation and
# updater-image requirements are defined in docs/UPDATE_CONTRACT.md.
#
# Inputs (env or args):
#   KIOSKY_REPO   path to kiosky-player working copy (default /home/builder/kiosky-player)
#   VERSION       explicit version string; default: homolog-<UTC timestamp>
#   CHANNEL       lab | homologation (default). stable is blocked for C18.
#   OUT_BASE      output base dir (default releases/app-updates)
#   --prepare-only   inspect inputs, print plan, do not write tar/manifest
#   --build-package  build tar.gz + manifest (default)
#   --allow-dirty    permit non-clean working tree (warn only)
#
# Outputs in OUT_BASE/<VERSION>/:
#   dadooh-kiosky-player-<VERSION>.tar.gz
#   dadooh-kiosky-player-<VERSION>.manifest.json
#
# Does NOT publish. Does NOT touch the device. Does NOT include secrets.

set -euo pipefail

# ----- defaults -----
KIOSKY_REPO="${KIOSKY_REPO:-/home/builder/kiosky-player}"
COMPONENT="kiosky-player"
CHANNEL="${CHANNEL:-homologation}"
OUT_BASE="${OUT_BASE:-releases/app-updates}"
SOURCE_REPO_FULL="${SOURCE_REPO_FULL:-dadoohai/kiosky-player}"
DEVICE_REQUIRED="orangepizero3"
BASE_IMAGE_MIN="c13.1.3"
ENTRYPOINT="kiosk.py"

MODE="build-package"
ALLOW_DIRTY=0
VERSION_OVERRIDE="${VERSION:-}"

# ----- args -----
for arg in "$@"; do
  case "$arg" in
    --prepare-only) MODE="prepare-only" ;;
    --build-package) MODE="build-package" ;;
    --allow-dirty) ALLOW_DIRTY=1 ;;
    --version=*) VERSION_OVERRIDE="${arg#*=}" ;;
    --kiosky-repo=*) KIOSKY_REPO="${arg#*=}" ;;
    --out-base=*) OUT_BASE="${arg#*=}" ;;
    --channel=*) CHANNEL="${arg#*=}" ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *)
      echo "FATAL: unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

log() { printf '[build_kiosky_player_release_package] %s\n' "$*"; }
die() { printf '[build_kiosky_player_release_package] FATAL: %s\n' "$*" >&2; exit 1; }

if [[ "${ALLOW_C18_FROZEN_PLAYER_RELEASE:-0}" != "1" ]]; then
  die "kiosky-player OTA packaging is frozen for C18; use image/homologation. ALLOW_C18_FROZEN_PLAYER_RELEASE=1 is only a legacy lab reproduction bypass, not approval for a C18-aware player-runtime release"
fi

# ----- validate inputs -----
[[ -d "$KIOSKY_REPO/.git" ]] || die "KIOSKY_REPO ($KIOSKY_REPO) is not a git repo"
[[ -f "$KIOSKY_REPO/$ENTRYPOINT" ]] || die "entrypoint $ENTRYPOINT not found in $KIOSKY_REPO"

# ----- collect git metadata -----
pushd "$KIOSKY_REPO" >/dev/null
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
  die "kiosky-player working tree is dirty (use --allow-dirty to override)"
fi

# ----- version -----
if [[ -z "$VERSION_OVERRIDE" ]]; then
  VERSION="homolog-$(date -u +%Y%m%d-%H%M%S)-${SOURCE_COMMIT_SHORT}"
else
  VERSION="$VERSION_OVERRIDE"
fi

# version must be path-safe
if ! [[ "$VERSION" =~ ^[A-Za-z0-9._-]+$ ]]; then
  die "version contains unsafe characters: $VERSION"
fi

if ! [[ "$CHANNEL" =~ ^(lab|homologation)$ ]]; then
  die "unsupported channel: $CHANNEL (legacy kiosky-player C18 builder only supports lab or homologation)"
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
log "dirty           = $DIRTY"
log "out_dir         = $OUT_DIR"
log "mode            = $MODE"

if [[ "$MODE" == "prepare-only" ]]; then
  log "prepare_only=true"
  log "would_build_payload=${PAYLOAD_PATH}"
  log "would_build_manifest=${MANIFEST_PATH}"
  exit 0
fi

# ----- stage tracked files via git archive -----
STAGE_DIR="$(mktemp -d -t kiosky-stage-XXXXXX)"
cleanup() { rm -rf "$STAGE_DIR"; }
trap cleanup EXIT

# git archive emits only tracked files; auto-excludes .git, __pycache__ (if gitignored), .venv, etc.
pushd "$KIOSKY_REPO" >/dev/null
git archive --format=tar HEAD | tar -x -C "$STAGE_DIR"
popd >/dev/null

# ----- forbidden file scan (defense in depth) -----
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

# ----- C18 legacy boundary scan -----
# Even with the explicit frozen-player bypass, this historical helper must not
# smuggle media-system, field-data, service, or image-owned files into a package.
while IFS= read -r -d '' path; do
  rel="${path#"$STAGE_DIR"/}"
  base="$(basename "$rel")"
  case "$rel" in
    data|data/*|*/data|*/data/*|media|media/*|*/media|*/media/*|cache|cache/*|*/cache|*/cache/*|config|config/*|*/config|*/config/*|secrets|secrets/*|*/secrets|*/secrets/*)
      die "C18 legacy boundary violation in staged tree: $rel"
      ;;
    opt|opt/*|*/opt|*/opt/*|usr|usr/*|*/usr|*/usr/*|boot|boot/*|*/boot|*/boot/*|lib/modules|lib/modules/*|*/lib/modules|*/lib/modules/*|etc/systemd|etc/systemd/*|*/etc/systemd|*/etc/systemd/*)
      die "C18 legacy boundary violation in staged tree: $rel"
      ;;
  esac
  case "$base" in
    mpv|ffmpeg|ffprobe|playlist.json|state.json|cache_index.json|seed.json|policy.json|*.service|*.timer|*.ko)
      die "C18 legacy boundary violation in staged tree: $rel"
      ;;
  esac
done < <(find "$STAGE_DIR" -mindepth 1 -print0)

# ----- secret scan (regex defense in depth) -----
SCAN_PATTERNS=(
  '-----BEGIN [A-Z ]+PRIVATE KEY-----'
  'AKIA[0-9A-Z]{16}'
  'ghp_[A-Za-z0-9]{30,}'
  'gho_[A-Za-z0-9]{30,}'
  'ghs_[A-Za-z0-9]{30,}'
  'github_pat_[A-Za-z0-9_]{30,}'
)
SCAN_REGEX="$(IFS='|'; echo "${SCAN_PATTERNS[*]}")"
SCAN_HITS_FILE="$(mktemp)"
trap 'rm -rf "$STAGE_DIR" "$SCAN_HITS_FILE"' EXIT

if grep -rEl --binary-files=without-match "$SCAN_REGEX" "$STAGE_DIR" > "$SCAN_HITS_FILE" 2>/dev/null; then
  if [[ -s "$SCAN_HITS_FILE" ]]; then
    log "secret scan hits (paths only, content NOT printed):"
    sed "s|^${STAGE_DIR}/||" "$SCAN_HITS_FILE" >&2
    die "secret-like content found in staged tree; aborting"
  fi
fi

# ----- build payload -----
mkdir -p "$OUT_DIR"

# deterministic: fixed mtime, ordered, numeric owners
tar \
  --owner=0 --group=0 --numeric-owner \
  --sort=name \
  --mtime="@${SOURCE_COMMIT_EPOCH}" \
  -czf "$PAYLOAD_PATH" \
  -C "$STAGE_DIR" .

PAYLOAD_BYTES="$(stat -c '%s' "$PAYLOAD_PATH")"
PAYLOAD_SHA256="$(sha256sum "$PAYLOAD_PATH" | awk '{print $1}')"

NOW_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# ----- manifest -----
# Use a small inline python to emit valid JSON deterministically.
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
    "payload": "${PAYLOAD_NAME}",
    "payload_sha256": "${PAYLOAD_SHA256}",
    "payload_bytes": ${PAYLOAD_BYTES},
    "entrypoint": "${ENTRYPOINT}",
    "requires": {
        "device": "${DEVICE_REQUIRED}",
        "base_image_min": "${BASE_IMAGE_MIN}"
    },
    "created_at_utc": "${NOW_UTC}"
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, sort_keys=True)
    f.write("\n")
PY

# verify manifest is parseable
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$MANIFEST_PATH" \
  || die "manifest JSON failed to validate"

log "build_package=true"
log "payload_path=${PAYLOAD_PATH}"
log "manifest_path=${MANIFEST_PATH}"
log "payload_sha256=${PAYLOAD_SHA256}"
log "payload_bytes=${PAYLOAD_BYTES}"
log "source_commit=${SOURCE_COMMIT}"
log "version=${VERSION}"
