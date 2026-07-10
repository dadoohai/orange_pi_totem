#!/usr/bin/env bash
# C18 - Publish a governed player-runtime release asset set to GitHub Releases.
#
# This is a publication route only. It does not touch a board, enable auto-pull,
# execute public thaw, or modify the updater rc=44 freeze. It re-runs the public
# thaw activation gate immediately before assembling assets.

set -euo pipefail

REPO="${REPO:-dadoohai/orange_pi_totem}"
RELEASE_DIR=""
H2_READINESS=""
STABLE_PROMOTION=""
OPERATOR_THAW=""
SERVER_SIDE_TRUSTED_KEY=""
SERVER_SIDE_TRUST_ANCHOR=""
TAG_OVERRIDE=""
TITLE_OVERRIDE=""
DRAFT=0
PRERELEASE="no"
MODE="prepare-only"

while [[ $# -gt 0 ]]; do
  arg="$1"
  case "$arg" in
    --release-dir=*) RELEASE_DIR="${arg#*=}" ;;
    --release-dir) shift; RELEASE_DIR="${1:-}" ;;
    --h2-readiness=*) H2_READINESS="${arg#*=}" ;;
    --h2-readiness) shift; H2_READINESS="${1:-}" ;;
    --stable-promotion-evidence=*) STABLE_PROMOTION="${arg#*=}" ;;
    --stable-promotion-evidence) shift; STABLE_PROMOTION="${1:-}" ;;
    --operator-thaw-decision=*) OPERATOR_THAW="${arg#*=}" ;;
    --operator-thaw-decision) shift; OPERATOR_THAW="${1:-}" ;;
    --server-side-trusted-key-pem=*) SERVER_SIDE_TRUSTED_KEY="${arg#*=}" ;;
    --server-side-trusted-key-pem) shift; SERVER_SIDE_TRUSTED_KEY="${1:-}" ;;
    --server-side-trust-anchor-evidence=*) SERVER_SIDE_TRUST_ANCHOR="${arg#*=}" ;;
    --server-side-trust-anchor-evidence) shift; SERVER_SIDE_TRUST_ANCHOR="${1:-}" ;;
    --repo=*) REPO="${arg#*=}" ;;
    --repo) shift; REPO="${1:-}" ;;
    --tag=*) TAG_OVERRIDE="${arg#*=}" ;;
    --tag) shift; TAG_OVERRIDE="${1:-}" ;;
    --title=*) TITLE_OVERRIDE="${arg#*=}" ;;
    --title) shift; TITLE_OVERRIDE="${1:-}" ;;
    --draft) DRAFT=1 ;;
    --prerelease) PRERELEASE="yes" ;;
    --no-prerelease) PRERELEASE="no" ;;
    --prepare-only) MODE="prepare-only" ;;
    --publish) MODE="publish" ;;
    -h|--help)
      sed -n '2,28p' "$0"
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

log() { printf '[publish_player_runtime_github_release] %s\n' "$*"; }
die() { printf '[publish_player_runtime_github_release] FATAL: %s\n' "$*" >&2; exit 1; }

[[ -n "$RELEASE_DIR" && -d "$RELEASE_DIR" ]] || die "missing or invalid --release-dir"
[[ -n "$H2_READINESS" && -f "$H2_READINESS" ]] || die "missing --h2-readiness"
[[ -n "$STABLE_PROMOTION" && -f "$STABLE_PROMOTION" ]] || die "missing --stable-promotion-evidence"
[[ -n "$OPERATOR_THAW" && -f "$OPERATOR_THAW" ]] || die "missing --operator-thaw-decision"
[[ -n "$SERVER_SIDE_TRUSTED_KEY" && -f "$SERVER_SIDE_TRUSTED_KEY" ]] || die "missing --server-side-trusted-key-pem"
[[ -n "$SERVER_SIDE_TRUST_ANCHOR" && -f "$SERVER_SIDE_TRUST_ANCHOR" ]] || die "missing --server-side-trust-anchor-evidence"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

shopt -s nullglob
MANIFESTS=( "$RELEASE_DIR"/dadooh-player-runtime-*.manifest.json )
PAYLOADS=( "$RELEASE_DIR"/dadooh-player-runtime-*.tar.gz )
RELEASE_GATES=( "$RELEASE_DIR"/c18-player-runtime-release-gate.json )
SERVER_SIDE_EVIDENCE=( "$RELEASE_DIR"/c18-server-side-publish-governance.json )
shopt -u nullglob

(( ${#MANIFESTS[@]} == 1 )) || die "expected exactly 1 player-runtime manifest in $RELEASE_DIR"
(( ${#PAYLOADS[@]} == 1 )) || die "expected exactly 1 player-runtime payload in $RELEASE_DIR"
(( ${#RELEASE_GATES[@]} == 1 )) || die "expected c18-player-runtime-release-gate.json in $RELEASE_DIR"
(( ${#SERVER_SIDE_EVIDENCE[@]} == 1 )) || die "expected c18-server-side-publish-governance.json in $RELEASE_DIR"

MANIFEST="${MANIFESTS[0]}"
PAYLOAD="${PAYLOADS[0]}"
RELEASE_GATE="${RELEASE_GATES[0]}"
SERVER_SIDE="${SERVER_SIDE_EVIDENCE[0]}"

read_json() {
  python3 -c '
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
val = d
for part in sys.argv[2].split("."):
    val = val[part]
print(val)
' "$1" "$2"
}

VERSION="$(read_json "$MANIFEST" version)"
COMPONENT="$(read_json "$MANIFEST" component)"
CHANNEL="$(read_json "$MANIFEST" channel)"
SOURCE_COMMIT="$(read_json "$MANIFEST" source_commit)"
PAYLOAD_SHA="$(read_json "$MANIFEST" payload_sha256)"
PAYLOAD_BASENAME="$(read_json "$MANIFEST" payload)"

[[ "$COMPONENT" == "player-runtime" ]] || die "manifest component is not player-runtime"
[[ "$CHANNEL" == "homologation" ]] || die "player-runtime publication must carry the governed homologation manifest"
[[ "$SOURCE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "manifest source_commit is not a full SHA"
[[ "$(basename "$PAYLOAD")" == "$PAYLOAD_BASENAME" ]] || die "payload basename mismatch"
ACTUAL_PAYLOAD_SHA="$(sha256sum "$PAYLOAD" | awk '{print $1}')"
[[ "$ACTUAL_PAYLOAD_SHA" == "$PAYLOAD_SHA" ]] || die "payload sha256 mismatch"

EXPECTED_TAG="player-runtime-${VERSION}"
if [[ -n "$TAG_OVERRIDE" && "$TAG_OVERRIDE" != "$EXPECTED_TAG" ]]; then
  die "tag override must exactly match ${EXPECTED_TAG}"
fi
TAG="${TAG_OVERRIDE:-$EXPECTED_TAG}"
[[ "$TAG" == "$EXPECTED_TAG" ]] || die "tag must exactly match ${EXPECTED_TAG}"
[[ "$TAG" =~ ^[A-Za-z0-9._-]+$ ]] || die "unsafe tag: $TAG"
TITLE="${TITLE_OVERRIDE:-Dadooh player-runtime ${VERSION}}"

NOW_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ACTIVATION_TMP="$(mktemp -t c18-player-runtime-activation-XXXXXX.json)"
SERVER_ASSETS_TMP="$(mktemp -t c18-player-runtime-server-assets-XXXXXX.json)"
REMOTE_REFS_TMP="$(mktemp -t c18-player-runtime-remote-XXXXXX.txt)"
READBACK_TMP="$(mktemp -t c18-player-runtime-readback-XXXXXX.json)"
NOTES_FILE=""
cleanup() {
  rm -f "$ACTIVATION_TMP" "$SERVER_ASSETS_TMP" "$REMOTE_REFS_TMP" "$READBACK_TMP"
  [[ -n "$NOTES_FILE" ]] && rm -f "$NOTES_FILE"
  return 0
}
trap cleanup EXIT

PYTHONDONTWRITEBYTECODE=1 python3 "$REPO_ROOT/scripts/qa/c18_player_runtime_public_thaw_activation_gate.py" \
  --h2-readiness "$H2_READINESS" \
  --stable-promotion-evidence "$STABLE_PROMOTION" \
  --operator-thaw-decision "$OPERATOR_THAW" \
  --release-gate-summary "$RELEASE_GATE" \
  --server-side-evidence "$SERVER_SIDE" \
  --server-side-trusted-key-pem "$SERVER_SIDE_TRUSTED_KEY" \
  --server-side-trust-anchor-evidence "$SERVER_SIDE_TRUST_ANCHOR" \
  --manifest "$MANIFEST" \
  --payload "$PAYLOAD" \
  --now-utc "$NOW_UTC" \
  --json >"$ACTIVATION_TMP" \
  || die "public thaw activation gate failed"

PYTHONDONTWRITEBYTECODE=1 python3 "$REPO_ROOT/scripts/qa/c18_server_side_publish_asset_collect.py" \
  --server-side-evidence "$SERVER_SIDE" \
  --trust-anchor-evidence "$SERVER_SIDE_TRUST_ANCHOR" \
  --expected-release-gate-sha256 "$(sha256sum "$RELEASE_GATE" | awk '{print $1}')" \
  --json >"$SERVER_ASSETS_TMP" \
  || die "server-side publish assets could not be collected"

mapfile -t SERVER_ASSETS < <(python3 - "$SERVER_ASSETS_TMP" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
for item in data["assets"]:
    print(item)
PY
)

ASSETS=()
append_asset() {
  local asset="$1"
  [[ -f "$asset" && ! -L "$asset" ]] || die "publish asset missing or symlink: $asset"
  local existing
  for existing in "${ASSETS[@]}"; do
    [[ "$existing" == "$asset" ]] && return 0
  done
  ASSETS+=( "$asset" )
}
for asset in "${SERVER_ASSETS[@]}"; do append_asset "$asset"; done
append_asset "$H2_READINESS"
append_asset "$STABLE_PROMOTION"
append_asset "$OPERATOR_THAW"
append_asset "$ACTIVATION_TMP"

git ls-remote --heads --tags "https://github.com/${REPO}.git" >"$REMOTE_REFS_TMP" \
  || die "failed to inspect remote refs for ${REPO}"

read -r REMOTE_SOURCE_COMMIT_PRESENT REMOTE_EXACT_TAG_PRESENT REMOTE_EXACT_TAG_VERIFIED < <(
  python3 - "$REMOTE_REFS_TMP" "$SOURCE_COMMIT" "$TAG" <<'PY'
import sys
from pathlib import Path

refs: list[tuple[str, str]] = []
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    parts = line.split()
    if len(parts) >= 2:
        refs.append((parts[0], parts[1]))
source_commit = sys.argv[2]
tag = sys.argv[3]
tag_refs = [
    sha for sha, ref in refs
    if ref == f"refs/tags/{tag}" or ref == f"refs/tags/{tag}^{{}}"
]
source_present = any(sha == source_commit for sha, _ref in refs)
tag_points_to_source = any(sha == source_commit for sha in tag_refs)
print(
    "1" if source_present or tag_points_to_source else "0",
    "1" if tag_refs else "0",
    "1" if tag_points_to_source else "0",
)
PY
)

log "repo=${REPO}"
log "tag=${TAG}"
log "title=${TITLE}"
log "mode=${MODE}"
log "component=${COMPONENT}"
log "manifest_channel=${CHANNEL}"
log "stable_decision_channel=stable"
log "version=${VERSION}"
log "source_commit=${SOURCE_COMMIT}"
log "payload_sha256=${PAYLOAD_SHA}"
log "activation_gate=passed"
log "asset_count=${#ASSETS[@]}"
log "remote_source_commit_present=${REMOTE_SOURCE_COMMIT_PRESENT}"
log "remote_exact_tag_present=${REMOTE_EXACT_TAG_PRESENT}"
log "remote_exact_tag_verified=${REMOTE_EXACT_TAG_VERIFIED}"
log "auto_pull_enabled=false"
log "public_thaw_executed=false"

if [[ "$MODE" == "prepare-only" ]]; then
  if [[ "$REMOTE_SOURCE_COMMIT_PRESENT" -eq 1 && "$REMOTE_EXACT_TAG_VERIFIED" -eq 1 ]]; then
    PUBLISH_ALLOWED_JSON="true"
    PUBLISH_BLOCKER_JSON="null"
  elif [[ "$REMOTE_SOURCE_COMMIT_PRESENT" -ne 1 ]]; then
    PUBLISH_ALLOWED_JSON="false"
    PUBLISH_BLOCKER_JSON="\"remote_source_commit_missing\""
  elif [[ "$REMOTE_EXACT_TAG_PRESENT" -ne 1 ]]; then
    PUBLISH_ALLOWED_JSON="false"
    PUBLISH_BLOCKER_JSON="\"remote_exact_tag_missing\""
  else
    PUBLISH_ALLOWED_JSON="false"
    PUBLISH_BLOCKER_JSON="\"remote_exact_tag_not_source_commit\""
  fi
  printf '{\n'
  printf '  "schema": "dadooh.c18.player_runtime.publication_prepare.v1",\n'
  printf '  "passed": true,\n'
  printf '  "would_publish": true,\n'
  printf '  "publish_allowed_now": %s,\n' "$PUBLISH_ALLOWED_JSON"
  printf '  "publish_blocker": %s,\n' "$PUBLISH_BLOCKER_JSON"
  printf '  "repo": "%s",\n' "$REPO"
  printf '  "tag": "%s",\n' "$TAG"
  printf '  "target_source_commit": "%s",\n' "$SOURCE_COMMIT"
  printf '  "asset_count": %s,\n' "${#ASSETS[@]}"
  printf '  "remote_exact_tag_verified": %s,\n' "$([[ "$REMOTE_EXACT_TAG_VERIFIED" -eq 1 ]] && printf true || printf false)"
  printf '  "non_claims": ["this_prepare_does_not_publish", "this_prepare_does_not_enable_auto_pull", "this_prepare_does_not_execute_public_thaw"]\n'
  printf '}\n'
  exit 0
fi

[[ "${ALLOW_C18_PLAYER_RUNTIME_PUBLICATION:-0}" == "1" ]] \
  || die "publish requires ALLOW_C18_PLAYER_RUNTIME_PUBLICATION=1"
[[ "$REMOTE_SOURCE_COMMIT_PRESENT" -eq 1 ]] \
  || die "source commit is not present in remote refs for ${REPO}; push/sync before publish"
[[ "$REMOTE_EXACT_TAG_PRESENT" -eq 1 ]] \
  || die "remote tag '${TAG}' is not present on ${REPO}; create/push the exact governed tag before publish"
[[ "$REMOTE_EXACT_TAG_VERIFIED" -eq 1 ]] \
  || die "remote tag '${TAG}' does not point to source commit ${SOURCE_COMMIT}"
command -v gh >/dev/null 2>&1 || { echo "GITHUB_CLI_NOT_AUTHENTICATED" >&2; die "gh CLI not installed"; }
if ! gh auth status >/dev/null 2>&1; then
  echo "GITHUB_CLI_NOT_AUTHENTICATED" >&2
  die "gh auth status failed; not publishing"
fi
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  die "release with tag '$TAG' already exists on $REPO"
fi

latest_tag() {
  local out
  out="$(gh release view --repo "$REPO" --json tagName 2>/dev/null)" \
    || die "failed to inspect current latest release for ${REPO}"
  python3 -c 'import json, sys; tag = json.load(sys.stdin).get("tagName") or ""; print(tag); sys.exit(0 if tag else 1)' <<<"$out" \
    || die "failed to parse current latest release for ${REPO}"
}

LATEST_BEFORE="$(latest_tag)"
log "latest_before=${LATEST_BEFORE:-none}"

NOTES_FILE="$(mktemp -t c18-player-runtime-notes-XXXXXX.md)"
{
  echo "# Dadooh player-runtime ${VERSION}"
  echo
  echo "Component: \`player-runtime\`"
  echo "Manifest channel: \`${CHANNEL}\`"
  echo "Stable decision: artifact-bound in \`$(basename "$STABLE_PROMOTION")\`"
  echo "Source commit: \`${SOURCE_COMMIT}\`"
  echo "Payload SHA256: \`${PAYLOAD_SHA}\`"
  echo
  echo "Non-claims: this release does not enable auto-pull and does not execute public thaw by itself."
} >"$NOTES_FILE"

GH_ARGS=(release create "$TAG" --repo "$REPO" --title "$TITLE" --notes-file "$NOTES_FILE" --target "$SOURCE_COMMIT" --verify-tag --latest=false)
[[ "$PRERELEASE" == "yes" ]] && GH_ARGS+=(--prerelease)
[[ "$DRAFT" -eq 1 ]] && GH_ARGS+=(--draft)

log "calling: gh ${GH_ARGS[*]} -- <validated-assets>"
RELEASE_URL="$(gh "${GH_ARGS[@]}" -- "${ASSETS[@]}")"
log "release_url=${RELEASE_URL}"

gh release view "$TAG" --repo "$REPO" --json tagName,isDraft,isPrerelease,targetCommitish >"$READBACK_TMP" \
  || die "published release could not be inspected"
python3 - "$READBACK_TMP" "$TAG" "$SOURCE_COMMIT" "$DRAFT" "$PRERELEASE" <<'PY' \
  || die "published release metadata does not match the governed target"
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
tag = sys.argv[2]
source_commit = sys.argv[3]
expected_draft = sys.argv[4] == "1"
expected_prerelease = sys.argv[5] == "yes"
if data.get("tagName") != tag:
    raise SystemExit("tagName mismatch")
if data.get("isDraft") is not expected_draft:
    raise SystemExit("isDraft mismatch")
if data.get("isPrerelease") is not expected_prerelease:
    raise SystemExit("isPrerelease mismatch")
if data.get("targetCommitish") != source_commit:
    raise SystemExit("targetCommitish mismatch")
PY

LATEST_AFTER="$(latest_tag)"
[[ "$LATEST_AFTER" == "$LATEST_BEFORE" ]] \
  || die "latest release drifted during governed publish: before='${LATEST_BEFORE:-none}' after='${LATEST_AFTER:-none}'"
log "latest_after=${LATEST_AFTER:-none}"
log "published=true"
