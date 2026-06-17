#!/usr/bin/env python3
"""Build an operator runbook from a C18 H2 power-loss matrix plan.

This tool is offline-only. It renders the already computed matrix plan into a
human checklist plus helper shell snippets, but it does not run SSH, execute
board commands, pull evidence, claim 17/17 coverage, or replace the required
physical power cut.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.player_runtime.powerloss_operator_runbook.v1"
PLAN_SCHEMA = "dadooh.c18.player_runtime.powerloss_matrix_plan.v1"
README_NAME = "README.md"
RUNBOOK_NAME = "operator-runbook.md"
PULL_SCRIPT_NAME = "pull-and-validate-evidence.sh"
MANIFEST_NAME = "operator-runbook-manifest.json"
PREFLIGHT_COLLECTOR = "scripts/board/c18_player_runtime_h2_powerloss_preflight_collect.py"
PREFLIGHT_GATE = "scripts/qa/c18_player_runtime_h2_powerloss_preflight_gate.py"
NON_CLAIMS = (
    "this_runbook_is_not_powerloss_evidence",
    "this_runbook_does_not_claim_17_17",
    "this_runbook_does_not_execute_board_commands",
    "this_runbook_does_not_pull_or_validate_evidence_by_itself",
    "this_runbook_does_not_replace_physical_power_cut",
    "this_runbook_does_not_authorize_stable_or_production",
    "this_runbook_does_not_thaw_player_runtime",
    "this_runbook_does_not_publish_or_fetch_releases",
    "remote_reboot_is_not_acceptable_powerloss_evidence",
)


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json_not_object:{path}")
    return data


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def command_block(lines: list[str]) -> str:
    body = "\n".join(line.rstrip() for line in lines if line.rstrip())
    return f"```sh\n{body}\n```"


def validate_plan(plan: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if plan.get("schema") != PLAN_SCHEMA:
        blockers.append("plan_schema_mismatch")
    commands = plan.get("commands_for_missing_checkpoints")
    if not isinstance(commands, list):
        blockers.append("plan_commands_missing")
        return blockers
    missing = plan.get("missing_checkpoints")
    if not isinstance(missing, list):
        blockers.append("plan_missing_checkpoints_missing")
        missing = []
    command_checkpoints = []
    for index, item in enumerate(commands):
        if not isinstance(item, dict):
            blockers.append(f"plan_command_not_object:{index}")
            continue
        checkpoint = item.get("checkpoint")
        if not isinstance(checkpoint, str) or not checkpoint:
            blockers.append(f"plan_command_checkpoint_missing:{index}")
        else:
            command_checkpoints.append(checkpoint)
        if item.get("requires_physical_cut") is not True:
            blockers.append(f"{checkpoint or index}:physical_cut_not_required")
        if not isinstance(item.get("arm"), list) or not item.get("arm"):
            blockers.append(f"{checkpoint or index}:arm_command_missing")
        if not isinstance(item.get("resume_after_power_restore"), list) or not item.get("resume_after_power_restore"):
            blockers.append(f"{checkpoint or index}:resume_command_missing")
        if item.get("requires_custom_setup") is True:
            setup = item.get("setup_before_arm")
            manual = item.get("manual_setup_instructions")
            has_setup_commands = isinstance(setup, list) and bool(setup)
            has_manual_instructions = isinstance(manual, list) and bool(manual)
            if not has_setup_commands and not has_manual_instructions:
                blockers.append(f"{checkpoint or index}:custom_setup_missing")
        notes = " ".join(str(note) for note in item.get("notes", []))
        if "remote reboot is not acceptable evidence" not in notes:
            blockers.append(f"{checkpoint or index}:remote_reboot_nonclaim_missing")
    if sorted(command_checkpoints) != sorted(str(item) for item in missing):
        blockers.append("plan_missing_commands_mismatch")
    return blockers


def runbook_manifest(plan: dict[str, Any], args: argparse.Namespace, generated_at: str) -> dict[str, Any]:
    commands = plan.get("commands_for_missing_checkpoints") or []
    checkpoints = []
    for item in commands:
        if not isinstance(item, dict):
            continue
        checkpoints.append({
            "checkpoint": item.get("checkpoint"),
            "phase": item.get("phase"),
            "requires_custom_setup": item.get("requires_custom_setup") is True,
            "manual_setup_required": item.get("requires_custom_setup") is True
            and not bool(item.get("setup_before_arm")),
            "setup_precondition": item.get("setup_precondition"),
            "requires_physical_cut": item.get("requires_physical_cut") is True,
        })
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "source_plan": str(args.matrix_plan),
        "source_plan_schema": plan.get("schema"),
        "target_package": plan.get("target_package"),
        "board": plan.get("board"),
        "covered_checkpoints": plan.get("covered_checkpoints", []),
        "missing_checkpoints": plan.get("missing_checkpoints", []),
        "checkpoint_count": len(checkpoints),
        "checkpoints": checkpoints,
        "result_claim": "powerloss_operator_runbook_written",
        "board_host_placeholder": args.board_host,
        "local_evidence_root_placeholder": args.local_evidence_root,
        "preflight_local_output": args.preflight_local_output,
        "preflight_image_marker": args.image_marker,
        "preflight_expected_image_tag": args.expected_image_tag,
        "preflight_expected_image_marker_sha256": args.expected_image_marker_sha256,
        "preflight_max_age_sec": args.preflight_max_age_sec,
        "pull_helper_requires_fresh_local_root": True,
        "pull_helper_rejects_utc_placeholder": True,
        "non_claims": list(NON_CLAIMS),
    }


def render_readme(manifest: dict[str, Any]) -> str:
    board = manifest.get("board") if isinstance(manifest.get("board"), dict) else {}
    missing = manifest.get("missing_checkpoints") or []
    covered = manifest.get("covered_checkpoints") or []
    return f"""# C18 H2 Power-Loss Operator Runbook

Generated: `{manifest["generated_at_utc"]}`

This directory is not physical power-loss evidence. It is an operator aid built
from the offline matrix plan so the remaining H2 checkpoints can be run one at a
time without losing the non-claims.

## State

- Covered checkpoints in the source plan: {len(covered)}/17
- Missing checkpoints in the source plan: {len(missing)}/17
- Board bundle dir: `{board.get("bundle_dir")}`
- Board evidence root: `{board.get("evidence_root")}`
- Canary media: `{board.get("canary_media")}`

## Files

- `{RUNBOOK_NAME}`: per-checkpoint setup, arm and resume commands.
- `{PULL_SCRIPT_NAME}`: optional pull/validation helper; edit host/path first.
  It refuses a `<utc>` placeholder and refuses to reuse an existing local root.
- `{MANIFEST_NAME}`: machine-readable summary of this runbook.

Run the H2 board preflight gate before starting a physical checkpoint session.
The preflight is not power-loss evidence; it only checks the board/package/image
and session topology against the matrix plan.

## Non-Claims

{chr(10).join(f"- `{claim}`" for claim in manifest["non_claims"])}
"""


def render_checkpoint(index: int, total: int, item: dict[str, Any]) -> str:
    checkpoint = str(item.get("checkpoint"))
    lines = [
        f"## {index}. {checkpoint}",
        "",
        f"- Phase: `{item.get('phase')}`",
        f"- Setup precondition: `{item.get('setup_precondition')}`",
        f"- Requires custom setup: `{str(item.get('requires_custom_setup') is True).lower()}`",
        f"- Expected resume version: `{item.get('expected_resume_version') or item.get('expected_rolled_to') or 'n/a'}`",
        "",
    ]
    notes = item.get("notes") if isinstance(item.get("notes"), list) else []
    if notes:
        lines.append("Notes:")
        lines.extend(f"- {note}" for note in notes)
        lines.append("")
    setup = item.get("setup_before_arm")
    if isinstance(setup, list) and setup:
        lines.extend(["Setup before arm:", "", command_block(setup), ""])
    elif item.get("requires_custom_setup") is True:
        manual = item.get("manual_setup_instructions")
        if isinstance(manual, list) and manual:
            lines.append("Manual setup before arm:")
            lines.extend(f"- {instruction}" for instruction in manual)
            lines.extend([
                "",
                "Do not run the arm command until the custom setup has been completed and recorded.",
                "",
            ])
        else:
            lines.extend([
                "Setup before arm: BLOCKED - the plan marks this checkpoint as custom setup but provides no setup instructions.",
                "",
            ])
    else:
        lines.extend(["Setup before arm: none required by the plan.", ""])
    arm = item.get("arm") if isinstance(item.get("arm"), list) else []
    resume = item.get("resume_after_power_restore") if isinstance(item.get("resume_after_power_restore"), list) else []
    lines.extend([
        "Arm command:",
        "",
        command_block(arm),
        "",
        "Operator action:",
        "",
        "1. Wait until the command prints `CUT_POWER_NOW`.",
        "2. Remove physical power. Do not use remote reboot.",
        "3. Restore power and wait for SSH.",
        "4. Run the resume command below before starting the next checkpoint.",
        "",
        "Resume command:",
        "",
        command_block(resume),
        "",
        f"Progress marker: `{index}/{total}`.",
        "",
    ])
    return "\n".join(lines)


def render_runbook(plan: dict[str, Any], manifest: dict[str, Any]) -> str:
    commands = [item for item in plan.get("commands_for_missing_checkpoints", []) if isinstance(item, dict)]
    board = plan.get("board") if isinstance(plan.get("board"), dict) else {}
    body = [
        "# C18 H2 Power-Loss Checkpoint Runbook",
        "",
        "Run one checkpoint at a time. A checkpoint is not evidence until physical",
        "power has been removed after `CUT_POWER_NOW`, the board has booted again,",
        "the resume command has passed, and the evidence gate has accepted the",
        "pulled directory.",
        "",
        "Do not use remote reboot as a substitute for power loss.",
        "",
        "## Preflight Before Physical Session",
        "",
        "Collect this preflight from board stdout into a local file, then run the",
        "offline gate against the matrix plan. Do not start physical cuts if the",
        "gate is red.",
        "",
        "The collector execution is read-only: it inspects board/package/image",
        "state and prints JSON to stdout. The `scp`/`rm` lines below only stage and",
        "remove a temporary collector copy under `/tmp`; they are not power-loss",
        "evidence, do not create checkpoint evidence, and may be skipped when the",
        "collector is already present in the bundle.",
        "",
        command_block([
            f"scp {PREFLIGHT_COLLECTOR} {manifest['board_host_placeholder']}:/tmp/c18_player_runtime_h2_powerloss_preflight_collect.py",
            f"ssh {manifest['board_host_placeholder']} \\",
            f"  \"cd {command_quote(str(board.get('bundle_dir') or '/data/c18-h2-powerloss-bundle'))} && \\",
            "   PYTHONDONTWRITEBYTECODE=1 \\",
            f"   PYTHONPATH={command_quote(str(board.get('bundle_dir') or '/data/c18-h2-powerloss-bundle') + '/scripts/board')} \\",
            "   python3 -B /tmp/c18_player_runtime_h2_powerloss_preflight_collect.py \\",
            f"     --bundle-dir {command_quote(str(board.get('bundle_dir') or '/data/c18-h2-powerloss-bundle'))} \\",
            f"     --evidence-root {command_quote(str(board.get('evidence_root') or '/data/c18-evidence/h2-powerloss'))} \\",
            f"     --canary-media {command_quote(str(board.get('canary_media') or '/data/media/c18-canary-h264.mp4'))} \\",
            f"     --image-marker {command_quote(str(manifest['preflight_image_marker']))} \\",
            "     --json\" \\",
            f"  > {command_quote(str(manifest['preflight_local_output']))}",
            f"ssh {manifest['board_host_placeholder']} \\",
            "  \"rm -f /tmp/c18_player_runtime_h2_powerloss_preflight_collect.py\"",
            f"python3 {PREFLIGHT_GATE} \\",
            f"  --preflight {command_quote(str(manifest['preflight_local_output']))} \\",
            f"  --matrix-plan {command_quote(str(manifest['source_plan']))} \\",
            f"  --expect-image-tag {command_quote(str(manifest['preflight_expected_image_tag']))} \\",
            f"  --expect-image-marker-sha256 {command_quote(str(manifest['preflight_expected_image_marker_sha256']))} \\",
            f"  --max-age-sec {int(manifest['preflight_max_age_sec'])} \\",
            "  --json",
        ]),
        "",
    ]
    for index, item in enumerate(commands, start=1):
        body.append(render_checkpoint(index, len(commands), item))
    body.extend([
        "## Final Validation",
        "",
        "After all missing checkpoints are collected and copied into a local evidence",
        "directory, rerun the H2 readiness gate with all 17 physical power-loss",
        "evidence directories. H2 must remain blocked until 17/17 power-loss, soak",
        "24h, stable promotion, and formal thaw decision are all present.",
        "",
        "Non-claims:",
        "",
        *[f"- `{claim}`" for claim in manifest["non_claims"]],
        "",
    ])
    return "\n".join(body)


def shell_array(name: str, values: list[str]) -> str:
    quoted = " ".join("'" + value.replace("'", "'\"'\"'") + "'" for value in values)
    return f"{name}=({quoted})"


def command_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def render_pull_script(plan: dict[str, Any], args: argparse.Namespace) -> str:
    board = plan.get("board") if isinstance(plan.get("board"), dict) else {}
    remote_root = str(board.get("evidence_root") or "/data/c18-evidence/h2-c16fb3e")
    checkpoints = [str(item) for item in plan.get("missing_checkpoints", [])]
    return f"""#!/usr/bin/env bash
set -euo pipefail

# This helper only pulls and validates evidence after the physical trials have
# been run. It does not execute board commands and does not create evidence.

BOARD_HOST="${{1:-{args.board_host}}}"
LOCAL_ROOT="${{2:-{args.local_evidence_root}}}"
REMOTE_ROOT="{remote_root}"
{shell_array("CHECKPOINTS", checkpoints)}

if [[ "$LOCAL_ROOT" == *"<utc>"* ]]; then
  echo "LOCAL_ROOT still contains <utc>; choose a concrete fresh path" >&2
  exit 2
fi

if [[ -e "$LOCAL_ROOT" ]]; then
  echo "LOCAL_ROOT already exists; choose a fresh path to avoid mixing evidence" >&2
  exit 2
fi

mkdir -p "$LOCAL_ROOT/_validation"

for checkpoint in "${{CHECKPOINTS[@]}}"; do
  if [[ -e "$LOCAL_ROOT/$checkpoint" ]]; then
    echo "checkpoint directory already exists locally: $LOCAL_ROOT/$checkpoint" >&2
    exit 2
  fi
  echo "pulling $checkpoint"
  scp -r "$BOARD_HOST:$REMOTE_ROOT/$checkpoint" "$LOCAL_ROOT/"
  python3 scripts/qa/c18_player_runtime_powerloss_evidence_gate.py \\
    --run-dir "$LOCAL_ROOT/$checkpoint" \\
    --json > "$LOCAL_ROOT/_validation/$checkpoint-powerloss-evidence-gate.json"
done

echo "pulled ${{#CHECKPOINTS[@]}} checkpoint directories into $LOCAL_ROOT"
"""


def build(args: argparse.Namespace) -> dict[str, Any]:
    plan = read_json(args.matrix_plan)
    blockers = validate_plan(plan)
    if blockers:
        return {
            "schema": SCHEMA,
            "passed": False,
            "result_claim": "powerloss_operator_runbook_blocked",
            "blockers": blockers,
            "non_claims": list(NON_CLAIMS),
        }
    generated_at = utcnow()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = runbook_manifest(plan, args, generated_at)
    write_json(output_dir / MANIFEST_NAME, manifest)
    write_text(output_dir / README_NAME, render_readme(manifest))
    write_text(output_dir / RUNBOOK_NAME, render_runbook(plan, manifest))
    script_path = output_dir / PULL_SCRIPT_NAME
    write_text(script_path, render_pull_script(plan, args))
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)
    return {
        "schema": SCHEMA,
        "passed": True,
        "result_claim": "powerloss_operator_runbook_written",
        "output_dir": str(output_dir),
        "manifest": str(output_dir / MANIFEST_NAME),
        "runbook": str(output_dir / RUNBOOK_NAME),
        "pull_script": str(script_path),
        "missing_checkpoints": plan.get("missing_checkpoints", []),
        "non_claims": list(NON_CLAIMS),
    }


class OperatorRunbookBuildSelfTest(unittest.TestCase):
    def fixture_plan(self, root: Path) -> Path:
        plan = {
            "schema": PLAN_SCHEMA,
            "result_claim": "powerloss_matrix_plan_incomplete",
            "target_package": {
                "version": "c18.player-runtime-test",
                "source_commit": "a" * 40,
                "payload_sha256": "b" * 64,
            },
            "board": {
                "bundle_dir": "/data/c18-test-bundle",
                "evidence_root": "/data/c18-evidence/h2-test",
                "canary_media": "/data/media/c18-canary-h264.mp4",
            },
            "covered_checkpoints": [],
            "missing_checkpoints": ["after_payload_staged"],
            "commands_for_missing_checkpoints": [{
                "checkpoint": "after_payload_staged",
                "phase": "apply",
                "requires_physical_cut": True,
                "requires_custom_setup": False,
                "setup_precondition": "standard-target-apply",
                "arm": ["cd '/data/c18-test-bundle'", "python3 trial.py --phase arm-apply"],
                "resume_after_power_restore": ["cd '/data/c18-test-bundle'", "python3 trial.py --phase resume"],
                "expected_resume_version": "previous",
                "notes": [
                    "physical power must be removed only after CUT_POWER_NOW is printed and persisted",
                    "remote reboot is not acceptable evidence",
                ],
            }],
            "non_claims": ["this_plan_is_not_powerloss_evidence"],
        }
        path = root / "plan.json"
        write_json(path, plan)
        return path

    def test_writes_runbook_without_claiming_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.fixture_plan(root)
            args = argparse.Namespace(
                matrix_plan=plan,
                output_dir=root / "out",
                board_host="<board-host>",
                local_evidence_root="docs/evidence/c18-update-validation/<utc>-h2-powerloss",
                preflight_local_output="docs/evidence/c18-update-validation/<utc>-h2-powerloss-preflight.json",
                image_marker="/etc/dadooh/c18-hwdecode-lab-test-image",
                expected_image_tag="c18-hwdecode-lab-test",
                expected_image_marker_sha256="c" * 64,
                preflight_max_age_sec=4 * 60 * 60,
            )
            result = build(args)
            self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
            readme = (args.output_dir / README_NAME).read_text(encoding="utf-8")
            runbook = (args.output_dir / RUNBOOK_NAME).read_text(encoding="utf-8")
            pull_script = (args.output_dir / PULL_SCRIPT_NAME).read_text(encoding="utf-8")
            manifest = read_json(args.output_dir / MANIFEST_NAME)
        self.assertIn("not physical power-loss evidence", readme)
        self.assertIn("CUT_POWER_NOW", runbook)
        self.assertIn("Do not use remote reboot", runbook)
        self.assertIn("Preflight Before Physical Session", runbook)
        self.assertIn(PREFLIGHT_COLLECTOR, runbook)
        self.assertIn(PREFLIGHT_GATE, runbook)
        self.assertIn("scp scripts/board/c18_player_runtime_h2_powerloss_preflight_collect.py", runbook)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", runbook)
        self.assertIn("PYTHONPATH='/data/c18-test-bundle/scripts/board'", runbook)
        self.assertIn("python3 -B /tmp/c18_player_runtime_h2_powerloss_preflight_collect.py", runbook)
        self.assertIn("--image-marker '/etc/dadooh/c18-hwdecode-lab-test-image'", runbook)
        self.assertIn("rm -f /tmp/c18_player_runtime_h2_powerloss_preflight_collect.py", runbook)
        self.assertIn("only stage and", runbook)
        self.assertIn("--max-age-sec 14400", runbook)
        self.assertIn("c18-hwdecode-lab-test", runbook)
        self.assertIn("does not execute board commands", pull_script)
        self.assertIn("c18_player_runtime_powerloss_evidence_gate.py", pull_script)
        self.assertIn('"$LOCAL_ROOT/_validation/$checkpoint-powerloss-evidence-gate.json"', pull_script)
        self.assertNotIn('"$LOCAL_ROOT/$checkpoint/powerloss-evidence-gate.json"', pull_script)
        self.assertIn("this_runbook_does_not_claim_17_17", manifest["non_claims"])
        self.assertEqual(manifest["preflight_image_marker"], "/etc/dadooh/c18-hwdecode-lab-test-image")
        self.assertEqual(manifest["preflight_expected_image_marker_sha256"], "c" * 64)
        self.assertEqual(manifest["preflight_max_age_sec"], 4 * 60 * 60)

    def test_custom_setup_requires_commands_or_manual_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.fixture_plan(root)
            data = read_json(plan)
            data["missing_checkpoints"] = ["after_previous_symlink"]
            item = data["commands_for_missing_checkpoints"][0]
            item["checkpoint"] = "after_previous_symlink"
            item["requires_custom_setup"] = True
            item["setup_before_arm"] = []
            write_json(plan, data)
            args = argparse.Namespace(
                matrix_plan=plan,
                output_dir=root / "out",
                board_host="<board-host>",
                local_evidence_root="docs/evidence/c18-update-validation/<utc>-h2-powerloss",
                preflight_local_output="docs/evidence/c18-update-validation/<utc>-h2-powerloss-preflight.json",
                image_marker="/etc/dadooh/c18-hwdecode-lab-test-image",
                expected_image_tag="c18-hwdecode-lab-test",
                expected_image_marker_sha256="c" * 64,
                preflight_max_age_sec=4 * 60 * 60,
            )
            blocked = build(args)
            data["commands_for_missing_checkpoints"][0]["manual_setup_instructions"] = [
                "Confirm old current exists and differs from target before arm.",
            ]
            write_json(plan, data)
            result = build(args)
            runbook = (args.output_dir / RUNBOOK_NAME).read_text(encoding="utf-8")
            pull_script = (args.output_dir / PULL_SCRIPT_NAME).read_text(encoding="utf-8")
            manifest = read_json(args.output_dir / MANIFEST_NAME)

        self.assertFalse(blocked["passed"])
        self.assertIn("after_previous_symlink:custom_setup_missing", blocked["blockers"])
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
        self.assertIn("Manual setup before arm", runbook)
        self.assertIn("Confirm old current exists", runbook)
        self.assertNotIn("none emitted by the plan", runbook)
        self.assertTrue(manifest["checkpoints"][0]["manual_setup_required"])
        self.assertTrue(manifest["pull_helper_requires_fresh_local_root"])
        self.assertTrue(manifest["pull_helper_rejects_utc_placeholder"])
        self.assertIn('LOCAL_ROOT still contains <utc>', pull_script)
        self.assertIn('LOCAL_ROOT already exists', pull_script)
        self.assertIn('checkpoint directory already exists locally', pull_script)

    def test_invalid_plan_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "bad.json"
            write_json(plan, {"schema": "wrong", "commands_for_missing_checkpoints": []})
            args = argparse.Namespace(
                matrix_plan=plan,
                output_dir=root / "out",
                board_host="<board-host>",
                local_evidence_root="docs/evidence/c18-update-validation/<utc>-h2-powerloss",
                preflight_local_output="docs/evidence/c18-update-validation/<utc>-h2-powerloss-preflight.json",
                image_marker="/etc/dadooh/c18-hwdecode-lab-test-image",
                expected_image_tag="c18-hwdecode-lab-test",
                expected_image_marker_sha256="c" * 64,
                preflight_max_age_sec=4 * 60 * 60,
            )
            result = build(args)
        self.assertFalse(result["passed"])
        self.assertIn("plan_schema_mismatch", result["blockers"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--matrix-plan", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--board-host", default="<board-host>")
    parser.add_argument("--local-evidence-root", default="docs/evidence/c18-update-validation/<utc>-h2-powerloss")
    parser.add_argument("--preflight-local-output", default="docs/evidence/c18-update-validation/<utc>-h2-powerloss-preflight.json")
    parser.add_argument("--image-marker", default="/etc/dadooh/c18-hwdecode-lab-1x-image")
    parser.add_argument("--expected-image-tag", default="<expected-image-tag>")
    parser.add_argument("--expected-image-marker-sha256", default="<expected-image-marker-sha256>")
    parser.add_argument("--preflight-max-age-sec", type=int, default=4 * 60 * 60)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(OperatorRunbookBuildSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if args.matrix_plan is None or args.output_dir is None:
        raise SystemExit("--matrix-plan and --output-dir are required unless --self-test is used")
    result = build(args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} result={result['result_claim']}")
        if result.get("output_dir"):
            print(result["output_dir"])
        for blocker in result.get("blockers", []):
            print(f"- {blocker}")
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
