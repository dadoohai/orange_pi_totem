#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import json
import os
import subprocess
import sys
import time
from pathlib import Path


APPLY_ROOT = Path("/tmp/c21-player-runtime-apply")
MANIFEST = APPLY_ROOT / "manifest.json"
PAYLOAD = APPLY_ROOT / "payload.tar.gz"
CANARY = APPLY_ROOT / "canary.mp4"
RESULT = APPLY_ROOT / "lab-apply-result.json"
POLICY = APPLY_ROOT / "lab-policy.json"
SERVICE = "kiosky-player.service"


def run(cmd: list[str], timeout: int = 120) -> dict[str, object]:
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def load_updatectl():
    bin_dir = Path("/opt/totem/bin")
    if str(bin_dir) not in sys.path:
        sys.path.insert(0, str(bin_dir))
    loader = importlib.machinery.SourceFileLoader("totem_updatectl", str(bin_dir / "totem-updatectl"))
    updatectl = loader.load_module()
    sys.modules["totem_updatectl"] = updatectl
    return updatectl


def load_candidate_health():
    bin_dir = Path("/opt/totem/bin")
    loader = importlib.machinery.SourceFileLoader(
        "c18_player_runtime_candidate_health",
        str(bin_dir / "c18_player_runtime_candidate_health.py"),
    )
    return loader.load_module()


def configure_updatectl(updatectl) -> None:
    updatectl.DATA_ROOT = Path("/data")
    updatectl.UPDATES_DIR = updatectl.DATA_ROOT / "updates"
    updatectl.POLICY_FILE = POLICY
    updatectl.LOG_DIR = updatectl.DATA_ROOT / "logs"
    updatectl.LOG_FILE = updatectl.LOG_DIR / "totem-update.log"
    updatectl.TOKEN_FILE = updatectl.DATA_ROOT / "secrets" / "github-release-token"
    updatectl.configure_component("player-runtime")


def write_policy() -> None:
    payload = {
        "schema": "dadooh.totem.update.policy.v1",
        "device_channel": "homologation",
        "device_track": "c18-hwdecode",
        "allowed_components": ["player-runtime", "totem-core"],
        "allow_prerelease": True,
        "allow_downgrade": False,
    }
    POLICY.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def service_active() -> bool:
    return subprocess.run(["systemctl", "is-active", "--quiet", SERVICE], check=False).returncode == 0


def read_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def wait_for_runtime_status(version: str, timeout_sec: int = 120) -> dict[str, object]:
    deadline = time.time() + timeout_sec
    last_status: dict[str, object] = {}
    while time.time() < deadline:
        status = read_json(Path("/tmp/kiosky-status.json"))
        last_status = status
        current = status.get("current_item") if isinstance(status.get("current_item"), dict) else {}
        current_path = str(current.get("path") or "") if isinstance(current, dict) else ""
        if (
            status.get("playback_state") == "playing"
            and current_path.endswith(".h264.mp4")
            and status.get("black_screen_risk_reason") in (None, "")
        ):
            return {
                "passed": True,
                "status": status,
                "waited_for_version": version,
            }
        time.sleep(2)
    return {
        "passed": False,
        "status": last_status,
        "waited_for_version": version,
    }


def main() -> int:
    APPLY_ROOT.mkdir(parents=True, exist_ok=True)
    updatectl = load_updatectl()
    candidate_health = load_candidate_health()
    write_policy()
    configure_updatectl(updatectl)

    manifest = read_json(MANIFEST)
    version = str(manifest.get("version") or "unknown")
    before = {
        "service_active": service_active(),
        "state": read_json(Path("/data/player-runtime/state.json")),
        "status": read_json(Path("/tmp/kiosky-status.json")),
    }

    stop_result = run(["systemctl", "stop", SERVICE], timeout=120)

    def health_hook(release_dir: Path, identity: dict[str, object]) -> dict[str, object]:
        return candidate_health.run_candidate_health(
            release_dir,
            identity,
            config_template=Path("/data/config/config.json"),
            canary_media=CANARY,
            output_dir=APPLY_ROOT / "candidate-health",
            duration_sec=20.0,
            interval_sec=1.0,
            startup_wait_sec=5.0,
            panfrost_fault_policy="delta",
        )

    previous_hook = updatectl.PLAYER_RUNTIME_HEALTH_HOOK
    previous_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
    updatectl.PLAYER_RUNTIME_HEALTH_HOOK = health_hook
    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
    try:
        rc = updatectl._apply_from_manifest_path_unfrozen(
            MANIFEST,
            payload_url=None,
            source="lab-local:c21-image-transcode",
            payload_path_override=PAYLOAD,
        )
    finally:
        updatectl.PLAYER_RUNTIME_HEALTH_HOOK = previous_hook
        updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = previous_thaw

    start_result = run(["systemctl", "start", SERVICE], timeout=120)
    post_status = wait_for_runtime_status(version)
    after = {
        "service_active": service_active(),
        "state": read_json(Path("/data/player-runtime/state.json")),
        "status": read_json(Path("/tmp/kiosky-status.json")),
    }
    result = {
        "schema": "dadooh.c21.player_runtime_image_transcode_lab_apply.v1",
        "version": version,
        "apply_rc": rc,
        "passed": rc == 0 and post_status.get("passed") is True and after["service_active"] is True,
        "before": before,
        "stop_result": stop_result,
        "start_result": start_result,
        "post_status": post_status,
        "after": after,
        "candidate_health_dir": str(APPLY_ROOT / "candidate-health"),
        "manifest": str(MANIFEST),
        "payload": str(PAYLOAD),
        "canary": str(CANARY),
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
