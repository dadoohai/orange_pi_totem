#!/usr/bin/env bash
set -euo pipefail

# This helper only pulls and validates evidence after the physical trials have
# been run. It does not execute board commands for trials. After each pull, it
# materializes the local top-level manifest required by the evidence gate.

BOARD_HOST="${1:-<board-host>}"
LOCAL_ROOT="${2:-docs/evidence/c18-update-validation/<utc>-h2-powerloss-c16fb3e}"
REMOTE_ROOT="/data/c18-evidence/h2-c16fb3e"
SOURCE_COMMIT="c16fb3ed01f0ce25c8203e5fe1d60baf60a75749"
TARGET_PACKAGE_VERSION="c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e"
TARGET_PAYLOAD_SHA256="d74a552f364de0e454a01a6fe839a1581d16c1b74acb357dc92c28a3ec0524a7"
BOARD_IMAGE_MARKER="c18-hwdecode-lab-1x-image"
IMAGE_TAG="c18-hwdecode-lab-1x"
IMAGE_SHA256="1a853f569b5da9e856439897c95612d719fd3059f12349fa1040a6350c3df2f2"
IMAGE_MARKER_SHA256="59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e"
CHECKPOINTS=('after_payload_staged' 'after_release_dir_created' 'after_extract' 'after_state_verifying' 'after_health_passed' 'after_release_tree_fsync' 'after_marker_written' 'after_previous_symlink' 'after_state_success' 'before_stage_cleanup' 'rollback_after_identify_links' 'rollback_after_current_unlinked')
declare -A EXPECTED_ACTIVE_VERSION=(['after_extract']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_health_passed']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_marker_written']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_payload_staged']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_previous_symlink']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_release_dir_created']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_release_tree_fsync']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_state_success']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['after_state_verifying']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['before_stage_cleanup']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['rollback_after_identify_links']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b')
declare -A SETUP_EXPECTED_ACTIVE_VERSION=(['after_extract']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_health_passed']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_marker_written']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_payload_staged']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_previous_symlink']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_release_dir_created']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_release_tree_fsync']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_state_success']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['after_state_verifying']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' ['before_stage_cleanup']='c18.player-runtime-m6-a2-20260610T072826Z-29ff33b')
declare -A SETUP_CANDIDATE_VERSION=(['after_extract']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['after_health_passed']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['after_marker_written']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['after_payload_staged']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['after_previous_symlink']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['after_release_dir_created']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['after_release_tree_fsync']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['after_state_success']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['after_state_verifying']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['before_stage_cleanup']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['rollback_after_current_unlinked']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' ['rollback_after_identify_links']='c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e')
declare -A ROLLBACK_EXPECTATION=(['rollback_after_current_unlinked']='image-fallback-after-current-unlinked' ['rollback_after_identify_links']='data-current-after-identify-links')

if [[ "$LOCAL_ROOT" == *"<utc>"* ]]; then
  echo "LOCAL_ROOT still contains <utc>; choose a concrete fresh path" >&2
  exit 2
fi

if [[ -e "$LOCAL_ROOT" ]]; then
  echo "LOCAL_ROOT already exists; choose a fresh path to avoid mixing evidence" >&2
  exit 2
fi

mkdir -p "$LOCAL_ROOT/_validation"

for checkpoint in "${CHECKPOINTS[@]}"; do
  if [[ -e "$LOCAL_ROOT/$checkpoint" ]]; then
    echo "checkpoint directory already exists locally: $LOCAL_ROOT/$checkpoint" >&2
    exit 2
  fi
  echo "pulling $checkpoint"
  scp -r "$BOARD_HOST:$REMOTE_ROOT/$checkpoint" "$LOCAL_ROOT/"
  manifest_args=(
    --run-dir "$LOCAL_ROOT/$checkpoint"
    --checkpoint "$checkpoint"
    --source-commit "$SOURCE_COMMIT"
    --target-package-version "$TARGET_PACKAGE_VERSION"
    --target-payload-sha256 "$TARGET_PAYLOAD_SHA256"
    --board-image-marker "$BOARD_IMAGE_MARKER"
    --image-tag "$IMAGE_TAG"
    --image-sha256 "$IMAGE_SHA256"
    --image-marker-sha256 "$IMAGE_MARKER_SHA256"
  )
  if [[ -n "${EXPECTED_ACTIVE_VERSION[$checkpoint]:-}" ]]; then
    manifest_args+=(--expected-active-version "${EXPECTED_ACTIVE_VERSION[$checkpoint]}")
  fi
  if [[ -n "${SETUP_EXPECTED_ACTIVE_VERSION[$checkpoint]:-}" ]]; then
    manifest_args+=(--setup-expected-active-version "${SETUP_EXPECTED_ACTIVE_VERSION[$checkpoint]}")
  fi
  if [[ -n "${SETUP_CANDIDATE_VERSION[$checkpoint]:-}" ]]; then
    manifest_args+=(--setup-candidate-version "${SETUP_CANDIDATE_VERSION[$checkpoint]}")
  fi
  if [[ -n "${ROLLBACK_EXPECTATION[$checkpoint]:-}" ]]; then
    manifest_args+=(--rollback-expectation "${ROLLBACK_EXPECTATION[$checkpoint]}")
  fi
  python3 scripts/qa/c18_player_runtime_powerloss_evidence_manifest_build.py "${manifest_args[@]}" \
    --json > "$LOCAL_ROOT/_validation/$checkpoint-powerloss-manifest-build.json"
  python3 scripts/qa/c18_player_runtime_powerloss_evidence_gate.py \
    --run-dir "$LOCAL_ROOT/$checkpoint" \
    --json > "$LOCAL_ROOT/_validation/$checkpoint-powerloss-evidence-gate.json"
done

echo "pulled ${#CHECKPOINTS[@]} checkpoint directories into $LOCAL_ROOT"
