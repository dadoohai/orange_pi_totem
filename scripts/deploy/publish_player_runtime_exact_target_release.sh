#!/usr/bin/env bash
# C18 M5 - Publish the exact authorized player-runtime homologation target.
#
# This narrow route publishes only the manifest, payload, and release-gate
# assets for one hash-bound player-runtime homologation target. It does not
# create or push tags, promote stable, select latest, publish extra evidence,
# enable broad latest auto-pull, or silently create draft/prerelease releases.

set -euo pipefail

REPO="${REPO:-dadoohai/orange_pi_totem}"
RELEASE_DIR=""
AUTHORIZATION=""
MODE="prepare-only"

while [[ $# -gt 0 ]]; do
  arg="$1"
  case "$arg" in
    --release-dir=*) RELEASE_DIR="${arg#*=}" ;;
    --release-dir) shift; RELEASE_DIR="${1:-}" ;;
    --repo=*) REPO="${arg#*=}" ;;
    --repo) shift; REPO="${1:-}" ;;
    --authorization=*) AUTHORIZATION="${arg#*=}" ;;
    --authorization) shift; AUTHORIZATION="${1:-}" ;;
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

log() { printf '[publish_player_runtime_exact_target_release] %s\n' "$*"; }
die() { printf '[publish_player_runtime_exact_target_release] FATAL: %s\n' "$*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RELEASE_VALIDATOR="$REPO_ROOT/scripts/qa/c18_player_runtime_release_gate.py"
AUTHORIZATION_GATE="$REPO_ROOT/scripts/qa/c18_player_runtime_production_autopull_authorization_gate.py"

[[ -n "$RELEASE_DIR" && -d "$RELEASE_DIR" ]] || die "missing or invalid --release-dir"
[[ -n "$AUTHORIZATION" && -f "$AUTHORIZATION" && ! -L "$AUTHORIZATION" ]] \
  || die "missing or invalid --authorization (must be a regular file, not a symlink)"
[[ -f "$RELEASE_VALIDATOR" ]] || die "player-runtime release gate validator missing: $RELEASE_VALIDATOR"
[[ -f "$AUTHORIZATION_GATE" ]] || die "production auto-pull authorization gate missing: $AUTHORIZATION_GATE"

require_clean_repo() {
  pushd "$REPO_ROOT" >/dev/null
  local dirty=0
  git diff --quiet || dirty=1
  git diff --cached --quiet || dirty=1
  [[ -z "$(git ls-files --others --exclude-standard)" ]] || dirty=1
  popd >/dev/null
  [[ "$dirty" -eq 0 ]] || die "orange_pi_totem working tree is dirty; commit or stash before preparing exact M5 publication"
}

sha256_file() {
  sha256sum "$1" | awk '{print $1}'
}

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

require_clean_repo

shopt -s nullglob
MANIFESTS=( "$RELEASE_DIR"/dadooh-player-runtime-*.manifest.json )
PAYLOADS=( "$RELEASE_DIR"/dadooh-player-runtime-*.tar.gz )
RELEASE_GATES=( "$RELEASE_DIR"/c18-player-runtime-release-gate.json )
shopt -u nullglob

(( ${#MANIFESTS[@]} == 1 )) || die "expected exactly 1 player-runtime manifest in $RELEASE_DIR"
(( ${#PAYLOADS[@]} == 1 )) || die "expected exactly 1 player-runtime payload in $RELEASE_DIR"
(( ${#RELEASE_GATES[@]} == 1 )) || die "expected exactly 1 c18-player-runtime-release-gate.json in $RELEASE_DIR"

MANIFEST="${MANIFESTS[0]}"
PAYLOAD="${PAYLOADS[0]}"
RELEASE_GATE="${RELEASE_GATES[0]}"
ASSETS=( "$MANIFEST" "$PAYLOAD" "$RELEASE_GATE" )

for asset in "${ASSETS[@]}"; do
  [[ -f "$asset" && ! -L "$asset" ]] || die "publish asset missing or symlink: $asset"
done

VERSION="$(read_json "$MANIFEST" version)"
COMPONENT="$(read_json "$MANIFEST" component)"
CHANNEL="$(read_json "$MANIFEST" channel)"
SOURCE_REPO="$(read_json "$MANIFEST" source_repo)"
SOURCE_COMMIT="$(read_json "$MANIFEST" source_commit)"
SOURCE_DIRTY="$(read_json "$MANIFEST" source_dirty)"
PAYLOAD_SHA="$(read_json "$MANIFEST" payload_sha256)"
PAYLOAD_BASENAME="$(read_json "$MANIFEST" payload)"
PAYLOAD_BYTES="$(wc -c <"$PAYLOAD" | tr -d ' ')"

[[ "$VERSION" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || die "unsafe version string in manifest"
[[ "$COMPONENT" == "player-runtime" ]] || die "manifest component is not player-runtime"
[[ "$CHANNEL" == "homologation" ]] || die "exact M5 player-runtime publication requires homologation channel"
[[ "$SOURCE_REPO" == "$REPO" ]] || die "manifest source_repo does not match publish repo"
[[ "$SOURCE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "manifest source_commit is not a full lowercase SHA"
[[ "$SOURCE_DIRTY" == "False" || "$SOURCE_DIRTY" == "false" ]] || die "manifest source_dirty must be false"
[[ "$(basename "$PAYLOAD")" == "$PAYLOAD_BASENAME" ]] || die "payload basename mismatch"
ACTUAL_PAYLOAD_SHA="$(sha256_file "$PAYLOAD")"
[[ "$ACTUAL_PAYLOAD_SHA" == "$PAYLOAD_SHA" ]] || die "payload sha256 mismatch"

TAG="player-runtime-${VERSION}"
[[ "$TAG" =~ ^[A-Za-z0-9._-]+$ ]] || die "unsafe exact target tag: $TAG"
TITLE="Dadooh player-runtime ${VERSION}"

VALIDATED_GATE_TMP="$(mktemp -t c18-player-runtime-exact-gate-XXXXXX.json)"
AUTHORIZATION_TMP="$(mktemp -t c18-player-runtime-exact-auth-XXXXXX.json)"
REMOTE_REFS_TMP="$(mktemp -t c18-player-runtime-exact-remote-XXXXXX.txt)"
ASSETS_JSON_TMP="$(mktemp -t c18-player-runtime-exact-assets-XXXXXX.json)"
NOTES_FILE=""
VERIFY_DIR=""
cleanup() {
  rm -f "$VALIDATED_GATE_TMP" "$AUTHORIZATION_TMP" "$REMOTE_REFS_TMP" "$ASSETS_JSON_TMP"
  [[ -n "$NOTES_FILE" ]] && rm -f "$NOTES_FILE"
  [[ -n "$VERIFY_DIR" ]] && rm -rf "$VERIFY_DIR"
  return 0
}
trap cleanup EXIT

PYTHONDONTWRITEBYTECODE=1 python3 "$RELEASE_VALIDATOR" \
  --manifest "$MANIFEST" \
  --payload "$PAYLOAD" \
  >"$VALIDATED_GATE_TMP" \
  || die "player-runtime release gate validation failed"

python3 - "$RELEASE_GATE" "$VALIDATED_GATE_TMP" <<'PY' || die "release gate artifact does not match current manifest/payload validation"
import json
import sys
from pathlib import Path

provided = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
actual = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
if actual.get("schema") != "dadooh.c18.player_runtime.release_gate.v1" or actual.get("passed") is not True:
    raise SystemExit("current release gate did not pass")
if provided != actual:
    raise SystemExit("provided release gate JSON differs from current validator output")
package = provided.get("package")
if not isinstance(package, dict):
    raise SystemExit("release gate package block missing")
if package.get("component") != "player-runtime":
    raise SystemExit("release gate package component mismatch")
if package.get("channel") != "homologation":
    raise SystemExit("release gate package channel mismatch")
PY

MANIFEST_SHA="$(sha256_file "$MANIFEST")"
RELEASE_GATE_SHA="$(sha256_file "$RELEASE_GATE")"

PYTHONDONTWRITEBYTECODE=1 python3 "$AUTHORIZATION_GATE" \
  --authorization "$AUTHORIZATION" \
  --manifest "$MANIFEST" \
  --payload "$PAYLOAD" \
  --release-gate "$RELEASE_GATE" \
  --json >"$AUTHORIZATION_TMP" \
  || die "production auto-pull authorization gate failed"

python3 - "$AUTHORIZATION_TMP" "$MANIFEST_SHA" "$PAYLOAD_SHA" "$RELEASE_GATE_SHA" "$VERSION" "$SOURCE_COMMIT" "$TAG" "$REPO" "$PAYLOAD_BYTES" "$(basename "$MANIFEST")" "$(basename "$PAYLOAD")" "$(basename "$RELEASE_GATE")" <<'PY' \
  || die "production auto-pull authorization is incomplete or not hash-bound"
import json
import sys
from pathlib import Path
from typing import Any

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
(
    manifest_sha,
    payload_sha,
    gate_sha,
    version,
    source_commit,
    tag,
    repo,
    payload_bytes,
    manifest_name,
    payload_name,
    release_gate_name,
) = sys.argv[2:13]
if not isinstance(data, dict):
    raise SystemExit("authorization gate output must be a JSON object")
if data.get("passed") is not True:
    raise SystemExit("authorization gate did not pass")
blockers = data.get("blockers")
if blockers not in (None, []):
    raise SystemExit(f"authorization gate reported blockers: {blockers!r}")

target = data.get("target") if isinstance(data.get("target"), dict) else {}
if not target and isinstance(data.get("expected"), dict):
    target = data["expected"]
if not target:
    raise SystemExit("authorization gate target missing")

def first(*keys: str) -> Any:
    for key in keys:
        if key in target:
            return target[key]
    return None

required = {
    "component": "player-runtime",
    "channel": "homologation",
    "version": version,
    "source_commit": source_commit,
    "repo": repo,
}
for key, expected in required.items():
    if first(key) != expected:
        raise SystemExit(f"authorization {key} mismatch")
if first("tag", "tag_name") != tag:
    raise SystemExit("authorization tag mismatch")

for key, expected in {
    "manifest": manifest_sha,
    "payload": payload_sha,
    "release_gate": gate_sha,
}.items():
    actual = target.get(f"{key}_sha256")
    if actual != expected:
        raise SystemExit(f"authorization {key} sha256 mismatch")
for key, expected in {
    "manifest_name": manifest_name,
    "payload_name": payload_name,
}.items():
    actual = target.get(key)
    if actual is not None and actual != expected:
        raise SystemExit(f"authorization {key} mismatch")
release_gate_actual = target.get("release_gate_name") or target.get("release_gate_asset_name")
if release_gate_actual is not None and release_gate_actual != release_gate_name:
    raise SystemExit("authorization release_gate_name mismatch")
if target.get("payload_bytes") is not None and str(target.get("payload_bytes")) != payload_bytes:
    raise SystemExit("authorization payload_bytes mismatch")
PY

git ls-remote --heads --tags "https://github.com/${REPO}.git" >"$REMOTE_REFS_TMP" \
  || die "failed to inspect remote refs for ${REPO}"

python3 - "$REMOTE_REFS_TMP" "$SOURCE_COMMIT" "$TAG" <<'PY' \
  || die "source commit or exact tag is missing from remote refs"
import sys
from pathlib import Path

refs: list[tuple[str, str]] = []
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    parts = line.split()
    if len(parts) >= 2:
        refs.append((parts[0], parts[1]))
source_commit = sys.argv[2]
tag = sys.argv[3]
source_present = any(sha == source_commit for sha, _ref in refs)
tag_refs = [
    sha for sha, ref in refs
    if ref == f"refs/tags/{tag}" or ref == f"refs/tags/{tag}^{{}}"
]
tag_points_to_source = any(sha == source_commit for sha in tag_refs)
if not source_present:
    raise SystemExit("source commit is not present in remote refs")
if not tag_refs:
    raise SystemExit("exact tag is not present in remote refs")
if not tag_points_to_source:
    raise SystemExit("exact tag does not point to manifest source_commit")
PY

command -v gh >/dev/null 2>&1 || die "gh CLI not installed"

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

log "repo=${REPO}"
log "mode=${MODE}"
log "tag=${TAG}"
log "title=${TITLE}"
log "component=${COMPONENT}"
log "manifest_channel=${CHANNEL}"
log "version=${VERSION}"
log "source_commit=${SOURCE_COMMIT}"
log "asset_count=3"
log "manifest_sha256=${MANIFEST_SHA}"
log "payload_sha256=${PAYLOAD_SHA}"
log "release_gate_sha256=${RELEASE_GATE_SHA}"
log "authorization=$(basename "$AUTHORIZATION")"
log "authorization_gate=passed"
log "remote_source_commit_present=true"
log "remote_exact_tag_verified=true"
log "latest_before=${LATEST_BEFORE:-none}"
log "nonclaim_stable_promotion=false"
log "nonclaim_latest_update=false"
log "nonclaim_auto_pull_broad_latest=false"

if [[ "$MODE" == "prepare-only" ]]; then
  python3 - "$REPO" "$TAG" "$VERSION" "$SOURCE_COMMIT" "$LATEST_BEFORE" \
    "$MANIFEST" "$PAYLOAD" "$RELEASE_GATE" \
    "$MANIFEST_SHA" "$PAYLOAD_SHA" "$RELEASE_GATE_SHA" <<'PY'
import json
import sys
from pathlib import Path

repo, tag, version, source_commit, latest_before = sys.argv[1:6]
asset_paths = [Path(value) for value in sys.argv[6:9]]
asset_hashes = sys.argv[9:12]
print(json.dumps({
    "schema": "dadooh.c18.player_runtime.exact_target_publication_prepare.v1",
    "passed": True,
    "mode": "prepare-only",
    "would_publish": True,
    "repo": repo,
    "tag": tag,
    "version": version,
    "target_source_commit": source_commit,
    "manifest_channel": "homologation",
    "asset_count": 3,
    "assets": [
        {"name": path.name, "sha256": sha}
        for path, sha in zip(asset_paths, asset_hashes)
    ],
    "authorization_gate": "passed",
    "remote_source_commit_present": True,
    "remote_exact_tag_verified": True,
    "release_exists": False,
    "latest_before": latest_before,
    "latest_after": latest_before,
    "published": False,
    "non_claims": [
        "this_route_does_not_promote_stable",
        "this_route_does_not_update_latest",
        "this_route_does_not_create_or_push_tags",
        "this_route_does_not_publish_extra_assets",
        "this_route_does_not_enable_broad_latest_autopull",
        "this_route_does_not_create_draft_or_prerelease",
    ],
}, indent=2, sort_keys=True))
PY
  exit 0
fi

[[ "${ALLOW_C18_PLAYER_RUNTIME_EXACT_TARGET_PUBLICATION:-0}" == "1" ]] \
  || die "publish requires ALLOW_C18_PLAYER_RUNTIME_EXACT_TARGET_PUBLICATION=1"
if ! gh auth status >/dev/null 2>&1; then
  echo "GITHUB_CLI_NOT_AUTHENTICATED" >&2
  die "gh auth status failed; not publishing"
fi

NOTES_FILE="$(mktemp -t c18-player-runtime-exact-notes-XXXXXX.md)"
{
  echo "# Dadooh player-runtime ${VERSION}"
  echo
  echo "Component: \`player-runtime\`"
  echo "Manifest channel: \`homologation\`"
  echo "Exact tag: \`${TAG}\`"
  echo "Source commit: \`${SOURCE_COMMIT}\`"
  echo
  echo "Assets:"
  echo "- \`$(basename "$MANIFEST")\` sha256:\`${MANIFEST_SHA}\`"
  echo "- \`$(basename "$PAYLOAD")\` sha256:\`${PAYLOAD_SHA}\`"
  echo "- \`$(basename "$RELEASE_GATE")\` sha256:\`${RELEASE_GATE_SHA}\`"
  echo
  echo "Non-claims:"
  echo "- Does not promote stable."
  echo "- Does not update GitHub latest."
  echo "- Does not create or push tags."
  echo "- Does not publish extra evidence assets."
  echo "- Does not enable broad latest auto-pull."
  echo "- Does not create draft or prerelease releases."
} >"$NOTES_FILE"

GH_ARGS=(
  release create "$TAG"
  --repo "$REPO"
  --title "$TITLE"
  --notes-file "$NOTES_FILE"
  --target "$SOURCE_COMMIT"
  --verify-tag
  --latest=false
)

log "calling: gh ${GH_ARGS[*]} -- <exact-assets>"
RELEASE_URL="$(gh "${GH_ARGS[@]}" -- "${ASSETS[@]}")"
log "release_url=${RELEASE_URL}"

gh release view "$TAG" --repo "$REPO" --json tagName,isDraft,isPrerelease,targetCommitish,assets >"$ASSETS_JSON_TMP" \
  || die "published release could not be inspected"
python3 - "$ASSETS_JSON_TMP" "$TAG" "$SOURCE_COMMIT" "$(basename "$MANIFEST")" "$(basename "$PAYLOAD")" "$(basename "$RELEASE_GATE")" <<'PY' \
  || die "published release metadata/assets do not match the exact target"
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
tag = sys.argv[2]
source_commit = sys.argv[3]
expected = sorted(sys.argv[4:7])
if data.get("tagName") != tag:
    raise SystemExit("tagName mismatch")
if data.get("isDraft") is not False:
    raise SystemExit("published release is draft")
if data.get("isPrerelease") is not False:
    raise SystemExit("published release is prerelease")
target_commitish = data.get("targetCommitish")
if target_commitish != source_commit:
    raise SystemExit(f"targetCommitish mismatch: {target_commitish!r}")
assets = data.get("assets")
if not isinstance(assets, list):
    raise SystemExit("assets must be a list")
names = sorted(item.get("name") for item in assets if isinstance(item, dict))
if names != expected:
    raise SystemExit(f"asset names mismatch: {names!r} != {expected!r}")
PY

VERIFY_DIR="$(mktemp -d -t c18-player-runtime-exact-download-XXXXXX)"
for asset in "${ASSETS[@]}"; do
  gh release download "$TAG" --repo "$REPO" --dir "$VERIFY_DIR" --clobber --pattern "$(basename "$asset")" >/dev/null \
    || die "failed to download published asset $(basename "$asset") for hash verification"
  downloaded="$VERIFY_DIR/$(basename "$asset")"
  [[ -f "$downloaded" && "$(sha256_file "$downloaded")" == "$(sha256_file "$asset")" ]] \
    || die "published asset sha256 mismatch for $(basename "$asset")"
done

LATEST_AFTER="$(latest_tag)"
[[ "$LATEST_AFTER" == "$LATEST_BEFORE" ]] \
  || die "latest release drifted during exact target publish: before='${LATEST_BEFORE:-none}' after='${LATEST_AFTER:-none}'"

python3 - "$REPO" "$TAG" "$VERSION" "$SOURCE_COMMIT" "$RELEASE_URL" "$LATEST_BEFORE" "$LATEST_AFTER" \
  "$MANIFEST" "$PAYLOAD" "$RELEASE_GATE" \
  "$MANIFEST_SHA" "$PAYLOAD_SHA" "$RELEASE_GATE_SHA" <<'PY'
import json
import sys
from pathlib import Path

repo, tag, version, source_commit, release_url, latest_before, latest_after = sys.argv[1:8]
asset_paths = [Path(value) for value in sys.argv[8:11]]
asset_hashes = sys.argv[11:14]

print(json.dumps({
    "schema": "dadooh.c18.player_runtime.exact_target_publication_result.v1",
    "passed": True,
    "mode": "publish",
    "would_publish": True,
    "published": True,
    "repo": repo,
    "tag": tag,
    "version": version,
    "target_source_commit": source_commit,
    "manifest_channel": "homologation",
    "release_url": release_url,
    "asset_count": 3,
    "assets": [
        {"name": path.name, "sha256": sha}
        for path, sha in zip(asset_paths, asset_hashes)
    ],
    "authorization_gate": "passed",
    "remote_source_commit_present": True,
    "remote_exact_tag_verified": True,
    "release_exists": True,
    "latest_before": latest_before,
    "latest_after": latest_after,
    "non_claims": [
        "this_route_does_not_promote_stable",
        "this_route_does_not_update_latest",
        "this_route_does_not_create_or_push_tags",
        "this_route_does_not_publish_extra_assets",
        "this_route_does_not_enable_broad_latest_autopull",
        "this_route_does_not_create_draft_or_prerelease",
    ],
}, indent=2, sort_keys=True))
PY
