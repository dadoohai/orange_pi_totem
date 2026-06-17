#!/usr/bin/env bash
set -euo pipefail

# This helper only pulls and validates evidence after the physical trials have
# been run. It does not execute board commands and does not create evidence.

BOARD_HOST="${1:-<board-host>}"
LOCAL_ROOT="${2:-docs/evidence/c18-update-validation/<utc>-h2-powerloss-c16fb3e}"
REMOTE_ROOT="/data/c18-evidence/h2-c16fb3e"
CHECKPOINTS=('after_payload_staged' 'after_release_dir_created' 'after_extract' 'after_state_verifying' 'after_health_passed' 'after_release_tree_fsync' 'after_marker_written' 'after_previous_symlink' 'after_state_success' 'before_stage_cleanup' 'rollback_after_identify_links' 'rollback_after_current_unlinked')

mkdir -p "$LOCAL_ROOT"
mkdir -p "$LOCAL_ROOT/_validation"

for checkpoint in "${CHECKPOINTS[@]}"; do
  echo "pulling $checkpoint"
  scp -r "$BOARD_HOST:$REMOTE_ROOT/$checkpoint" "$LOCAL_ROOT/"
  python3 scripts/qa/c18_player_runtime_powerloss_evidence_gate.py \
    --run-dir "$LOCAL_ROOT/$checkpoint" \
    --json > "$LOCAL_ROOT/_validation/$checkpoint-powerloss-evidence-gate.json"
done

echo "pulled ${#CHECKPOINTS[@]} checkpoint directories into $LOCAL_ROOT"
