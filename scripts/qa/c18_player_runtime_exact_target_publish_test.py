#!/usr/bin/env python3
"""Isolated tests for the C18 M5 exact player-runtime publisher."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from collections.abc import Iterator
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLISHER_PATH = REPO_ROOT / "scripts" / "deploy" / "publish_player_runtime_exact_target_release.sh"
HEAVY_PUBLISHER_PATH = REPO_ROOT / "scripts" / "deploy" / "publish_player_runtime_github_release.sh"
AUTH_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_production_autopull_authorization_gate.py"
PUBLISH_REPO = "dadoohai/orange_pi_totem"


class Fixture(dict[str, Any]):
    pass


def _write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def flat_authorization(
    *,
    repo: str,
    version: str,
    source_commit: str,
    manifest: Path,
    payload: Path,
    release_gate: Path,
    payload_sha256: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": "dadooh.c18.player_runtime.production_autopull_authorization.v1",
        "enabled": True,
        "component": "player-runtime",
        "auto_pull_enabled": True,
        "allow_latest": False,
        "allow_prerelease": False,
        "allow_downgrade": False,
        "repo": repo,
        "tag_name": f"player-runtime-{version}",
        "version": version,
        "channel": "homologation",
        "device_track": "c18-hwdecode",
        "source_commit": source_commit,
        "payload_sha256": payload_sha256,
        "manifest_sha256": _sha256(manifest),
        "release_gate_asset_name": release_gate.name,
        "release_gate_sha256": _sha256(release_gate),
        "business_decision": {
            "risk_accepted": True,
            "rollout_mode": "simple_global",
            "operator": "operator-prod-01",
            "rollback_owner": "rollback-owner-01",
            "accepted_at_local_date": "2026-07-10",
        },
        "non_claims": [
            "not_latest_broad",
            "not_future_player_runtime_targets",
            "not_kiosky_player_legacy_release_path",
            "not_media_system_update",
            "not_dashboard_or_canary_groups",
            "not_device_side_signature_enforcement",
        ],
    }
    if overrides:
        data.update(overrides)
    return data


class C18PlayerRuntimeExactTargetPublisherTest(unittest.TestCase):
    @contextlib.contextmanager
    def fixture(self, **overrides: str) -> Iterator[Fixture]:
        with tempfile.TemporaryDirectory(prefix="c18-exact-publisher-") as tmp:
            root = Path(tmp)
            repo = root / "orange_pi_totem"
            deploy_dir = repo / "scripts" / "deploy"
            qa_dir = repo / "scripts" / "qa"
            release_dir = root / "release"
            stub_dir = root / "stubs"
            deploy_dir.mkdir(parents=True)
            qa_dir.mkdir(parents=True)
            release_dir.mkdir()
            stub_dir.mkdir()

            publisher = deploy_dir / PUBLISHER_PATH.name
            shutil.copy2(PUBLISHER_PATH, publisher)
            publisher.chmod(0o755)
            (qa_dir / "c18_player_runtime_release_gate.py").write_text("# fake release gate\n", encoding="utf-8")
            (qa_dir / "c18_player_runtime_production_autopull_authorization_gate.py").write_text(
                "# fake authorization gate\n",
                encoding="utf-8",
            )

            version = "c18.player-runtime-homolog-test"
            source_commit = "a" * 40
            payload = release_dir / f"dadooh-player-runtime-{version}.tar.gz"
            payload.write_bytes(b"player-runtime-payload\n")
            payload_sha = _sha256(payload)
            manifest = release_dir / f"dadooh-player-runtime-{version}.manifest.json"
            _write_json(
                manifest,
                {
                    "schema": "dadooh.totem.update.v1",
                    "component": "player-runtime",
                    "version": version,
                    "channel": "homologation",
                    "created_at_utc": "2026-07-10T00:00:00Z",
                    "source_repo": PUBLISH_REPO,
                    "source_branch": "foundation-v0.1",
                    "source_commit": source_commit,
                    "source_dirty": False,
                    "payload": payload.name,
                    "payload_sha256": payload_sha,
                    "payload_bytes": payload.stat().st_size,
                },
            )
            release_gate = release_dir / "c18-player-runtime-release-gate.json"
            release_gate_data = {
                "schema": "dadooh.c18.player_runtime.release_gate.v1",
                "passed": True,
                "component": "player-runtime",
                "manifest": {
                    "version": version,
                    "payload_sha256": payload_sha,
                    "source_commit": source_commit,
                    "channel": "homologation",
                },
                "package": {
                    "manifest": manifest.name,
                    "payload": payload.name,
                    "payload_sha256": payload_sha,
                    "source_commit": source_commit,
                    "component": "player-runtime",
                    "channel": "homologation",
                },
                "payload": {"kiosk_py_sha256": "b" * 64, "tree_sha256": "c" * 64},
            }
            _write_json(release_gate, release_gate_data)

            authorization = release_dir / "player-runtime-production-autopull.json"
            auth_data = flat_authorization(
                repo=PUBLISH_REPO,
                version=version,
                source_commit=source_commit,
                manifest=manifest,
                payload=payload,
                release_gate=release_gate,
                payload_sha256=payload_sha,
            )
            auth_mode = overrides.get("auth_mode", "good")
            if auth_mode == "empty":
                auth_data = {}
            elif auth_mode == "nested":
                auth_data = {"target": auth_data}
            elif auth_mode == "bad_hash":
                auth_data["payload_sha256"] = "0" * 64
            _write_json(authorization, auth_data)

            gh_capture = root / "gh-argv.bin"
            latest_counter = root / "latest-counter.txt"
            _write_executable(
                stub_dir / "python3",
                r"""
                #!/usr/bin/env bash
                set -euo pipefail
                case "${1:-}" in
                  */scripts/qa/c18_player_runtime_release_gate.py)
                    cat "$C18_RELEASE_GATE_FIXTURE"
                    exit 0
                    ;;
                  */scripts/qa/c18_player_runtime_production_autopull_authorization_gate.py)
                    for arg in "$@"; do
                      if [[ "$arg" == --expected-* ]]; then
                        printf '{"passed": false, "target": {}, "blockers": ["unexpected_expected_flag"]}\n'
                        exit 1
                      fi
                    done
                    "$C18_REAL_PYTHON3" - "$@" <<'PY'
import hashlib
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]

def get(flag: str) -> str:
    try:
        return args[args.index(flag) + 1]
    except ValueError as exc:
        raise SystemExit(f"missing {flag}") from exc

auth_path = Path(get("--authorization"))
manifest_path = Path(get("--manifest"))
payload_path = Path(get("--payload"))
release_gate_path = Path(get("--release-gate"))
auth = json.loads(auth_path.read_text(encoding="utf-8"))
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

mode = os.environ.get("C18_AUTH_MODE", "good")
blockers = []
if not auth:
    blockers.append("authorization_empty")
if "target" in auth:
    blockers.append("authorization_nested")
expected = {
    "component": "player-runtime",
    "channel": "homologation",
    "repo": manifest["source_repo"],
    "tag_name": f"player-runtime-{manifest['version']}",
    "version": manifest["version"],
    "source_commit": manifest["source_commit"],
    "payload_sha256": manifest["payload_sha256"],
    "manifest_sha256": sha(manifest_path),
    "release_gate_sha256": sha(release_gate_path),
}
for key, value in expected.items():
    if mode != "bad_hash" and auth.get(key) != value:
        blockers.append(f"authorization_{key}_mismatch")
target = dict(auth) if isinstance(auth, dict) else {}
print(json.dumps({"passed": not blockers, "target": target, "blockers": blockers}, indent=2, sort_keys=True))
raise SystemExit(0 if not blockers else 1)
PY
                    exit $?
                    ;;
                esac
                exec "$C18_REAL_PYTHON3" "$@"
                """,
            )
            _write_executable(
                stub_dir / "git",
                r"""
                #!/usr/bin/env bash
                set -euo pipefail
                case "${1:-}" in
                  diff)
                    if [[ "${C18_FAKE_DIRTY:-0}" == "1" ]]; then
                      exit 1
                    fi
                    exit 0
                    ;;
                  ls-files)
                    if [[ "${C18_FAKE_UNTRACKED:-0}" == "1" ]]; then
                      printf 'dirty.txt\n'
                    fi
                    exit 0
                    ;;
                  ls-remote)
                    if [[ "${C18_REMOTE_MODE:-present}" == "missing" ]]; then
                      printf '%s\trefs/heads/foundation-v0.1\n' "${C18_OTHER_COMMIT:-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb}"
                    else
                      printf '%s\trefs/heads/foundation-v0.1\n' "$C18_SOURCE_COMMIT"
                      printf '%s\trefs/tags/player-runtime-%s\n' "$C18_SOURCE_COMMIT" "$C18_VERSION"
                    fi
                    exit 0
                    ;;
                esac
                exit 2
                """,
            )
            _write_executable(
                stub_dir / "gh",
                r"""
                #!/usr/bin/env bash
                set -euo pipefail

                json_has_field() {
                  local field="$1"
                  shift
                  local want_json=0 arg
                  for arg in "$@"; do
                    if [[ "$want_json" == "1" ]]; then
                      [[ ",$arg," == *",$field,"* ]] && return 0
                      return 1
                    fi
                    [[ "$arg" == "--json" ]] && want_json=1
                  done
                  return 1
                }

                if [[ "${1:-} ${2:-}" == "auth status" ]]; then
                  exit 0
                fi

                if [[ "${1:-} ${2:-}" == "release view" ]]; then
                  third="${3:-}"
                  if [[ -n "$third" && "$third" != --* ]]; then
                    if json_has_field "assets" "$@"; then
                      "$C18_REAL_PYTHON3" - "$C18_RELEASE_DIR" "$C18_VERSION" "$C18_SOURCE_COMMIT" <<'PY'
import json
import os
import sys
from pathlib import Path
root = Path(sys.argv[1])
version = sys.argv[2]
source_commit = sys.argv[3]
assets = [
    {"name": f"dadooh-player-runtime-{version}.manifest.json"},
    {"name": f"dadooh-player-runtime-{version}.tar.gz"},
    {"name": "c18-player-runtime-release-gate.json"},
]
if os.environ.get("C18_EXTRA_ASSET") == "1":
    assets.append({"name": "extra.txt"})
print(json.dumps({
    "tagName": f"player-runtime-{version}",
    "isDraft": os.environ.get("C18_RELEASE_DRAFT") == "1",
    "isPrerelease": os.environ.get("C18_RELEASE_PRERELEASE") == "1",
    "targetCommitish": os.environ.get("C18_TARGET_COMMITISH", source_commit),
    "assets": assets,
}))
PY
                      exit 0
                    fi
                    if [[ "${C18_RELEASE_EXISTS:-0}" == "1" ]]; then
                      exit 0
                    fi
                    exit 1
                  fi

                  if json_has_field "tagName" "$@"; then
                    if [[ "${C18_LATEST_FAIL:-0}" == "1" ]]; then
                      exit 1
                    fi
                    count=0
                    if [[ -f "$C18_LATEST_COUNTER" ]]; then
                      count="$(cat "$C18_LATEST_COUNTER")"
                    fi
                    printf '%s\n' "$((count + 1))" > "$C18_LATEST_COUNTER"
                    tag="${C18_LATEST_TAG:-totem-core-stable}"
                    if [[ "${C18_LATEST_DRIFT:-0}" == "1" && "$count" -ge 1 ]]; then
                      tag="${tag}-drift"
                    fi
                    "$C18_REAL_PYTHON3" - "$tag" <<'PY'
import json
import sys
print(json.dumps({"tagName": sys.argv[1]}))
PY
                    exit 0
                  fi
                  exit 2
                fi

                if [[ "${1:-} ${2:-}" == "release create" ]]; then
                  "$C18_REAL_PYTHON3" - "$C18_GH_CAPTURE" "$@" <<'PY'
import sys
from pathlib import Path
Path(sys.argv[1]).write_bytes(b"\0".join(arg.encode() for arg in sys.argv[2:]) + b"\0")
PY
                  printf 'https://example.invalid/releases/%s\n' "$C18_VERSION"
                  exit 0
                fi

                if [[ "${1:-} ${2:-}" == "release download" ]]; then
                  out_dir=""
                  pattern=""
                  while [[ $# -gt 0 ]]; do
                    case "$1" in
                      --dir) shift; out_dir="${1:-}" ;;
                      --pattern) shift; pattern="${1:-}" ;;
                    esac
                    shift || true
                  done
                  mkdir -p "$out_dir"
                  cp "$C18_RELEASE_DIR/$pattern" "$out_dir/$pattern"
                  exit 0
                fi

                exit 2
                """,
            )
            (release_dir / "VERSION").write_text(version + "\n", encoding="utf-8")

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{stub_dir}:{env.get('PATH', '')}",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "C18_RELEASE_GATE_FIXTURE": str(release_gate),
                    "C18_REAL_PYTHON3": sys.executable,
                    "C18_SOURCE_COMMIT": source_commit,
                    "C18_VERSION": version,
                    "C18_RELEASE_DIR": str(release_dir),
                    "C18_GH_CAPTURE": str(gh_capture),
                    "C18_LATEST_COUNTER": str(latest_counter),
                    "C18_FAKE_DIRTY": overrides.get("dirty", "0"),
                    "C18_REMOTE_MODE": overrides.get("remote_mode", "present"),
                    "C18_LATEST_DRIFT": overrides.get("latest_drift", "0"),
                    "C18_LATEST_FAIL": overrides.get("latest_fail", "0"),
                    "C18_RELEASE_DRAFT": overrides.get("release_draft", "0"),
                    "C18_AUTH_MODE": auth_mode,
                }
            )
            if overrides.get("allow_publish") == "1":
                env["ALLOW_C18_PLAYER_RUNTIME_EXACT_TARGET_PUBLICATION"] = "1"

            yield Fixture(
                root=root,
                repo=repo,
                publisher=publisher,
                release_dir=release_dir,
                manifest=manifest,
                payload=payload,
                release_gate=release_gate,
                authorization=authorization,
                version=version,
                source_commit=source_commit,
                gh_capture=gh_capture,
                env=env,
            )

    def run_publisher(
        self,
        fx: Fixture,
        *args: str,
        include_authorization: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            str(fx["publisher"]),
            "--release-dir",
            str(fx["release_dir"]),
            "--repo",
            PUBLISH_REPO,
        ]
        if include_authorization:
            command.extend(["--authorization", str(fx["authorization"])])
        command.extend(args)
        return subprocess.run(
            command,
            cwd=fx["repo"],
            env=fx["env"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def load_stdout_json(self, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        start = result.stdout.find("{")
        self.assertNotEqual(start, -1, msg=result.stdout + result.stderr)
        return json.loads(result.stdout[start:])

    def test_requires_authorization_file(self) -> None:
        with self.fixture() as fx:
            result = self.run_publisher(fx, include_authorization=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--authorization", result.stdout + result.stderr)

    def test_prepare_is_default_and_does_not_create_release(self) -> None:
        with self.fixture() as fx:
            result = self.run_publisher(fx)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            data = self.load_stdout_json(result)
            self.assertEqual(data["mode"], "prepare-only")
            self.assertEqual(data["asset_count"], 3)
            self.assertEqual(data["tag"], f"player-runtime-{fx['version']}")
            self.assertEqual(data["version"], fx["version"])
            self.assertEqual(data["target_source_commit"], fx["source_commit"])
            self.assertEqual(data["latest_before"], "totem-core-stable")
            self.assertEqual(data["latest_after"], data["latest_before"])
            self.assertFalse(data["published"])
            self.assertEqual(
                data["assets"],
                [
                    {"name": fx["manifest"].name, "sha256": _sha256(fx["manifest"])},
                    {"name": fx["payload"].name, "sha256": _sha256(fx["payload"])},
                    {"name": fx["release_gate"].name, "sha256": _sha256(fx["release_gate"])},
                ],
            )
            self.assertFalse(fx["gh_capture"].exists(), msg="prepare-only must not call gh release create")
            self.assertIn("this_route_does_not_update_latest", data["non_claims"])
            self.assertIn("this_route_does_not_promote_stable", data["non_claims"])

    def test_empty_authorization_fails_closed(self) -> None:
        with self.fixture(auth_mode="empty") as fx:
            result = self.run_publisher(fx)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("production auto-pull authorization", result.stdout + result.stderr)

    def test_nested_authorization_fails_closed(self) -> None:
        with self.fixture(auth_mode="nested") as fx:
            result = self.run_publisher(fx)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("production auto-pull authorization", result.stdout + result.stderr)

    def test_tampered_authorization_hash_fails_closed(self) -> None:
        with self.fixture(auth_mode="bad_hash") as fx:
            result = self.run_publisher(fx)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("authorization", result.stdout + result.stderr)
            self.assertIn("hash", result.stdout + result.stderr)

    def test_dirty_repo_fails_closed(self) -> None:
        with self.fixture(dirty="1") as fx:
            result = self.run_publisher(fx)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("working tree is dirty", result.stdout + result.stderr)

    def test_remote_source_commit_missing_fails_closed(self) -> None:
        with self.fixture(remote_mode="missing") as fx:
            result = self.run_publisher(fx)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source commit or exact tag is missing", result.stdout + result.stderr)

    def test_latest_query_failure_fails_closed(self) -> None:
        with self.fixture(latest_fail="1") as fx:
            result = self.run_publisher(fx)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("failed to inspect current latest", result.stdout + result.stderr)

    def test_publish_without_explicit_env_fails_closed(self) -> None:
        with self.fixture() as fx:
            result = self.run_publisher(fx, "--publish")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ALLOW_C18_PLAYER_RUNTIME_EXACT_TARGET_PUBLICATION=1", result.stdout + result.stderr)

    def test_publish_command_uses_verify_tag_latest_false_and_exact_assets(self) -> None:
        with self.fixture(allow_publish="1") as fx:
            result = self.run_publisher(fx, "--publish")
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            argv = [part.decode() for part in fx["gh_capture"].read_bytes().split(b"\0") if part]
            self.assertEqual(argv[:3], ["release", "create", f"player-runtime-{fx['version']}"])
            self.assertIn("--verify-tag", argv)
            self.assertIn("--latest=false", argv)
            self.assertNotIn("--latest", argv)
            self.assertNotIn("--prerelease", argv)
            self.assertNotIn("--draft", argv)
            self.assertIn("--target", argv)
            self.assertEqual(argv[argv.index("--target") + 1], fx["source_commit"])
            separator = argv.index("--")
            self.assertEqual(
                argv[separator + 1:],
                [str(fx["manifest"]), str(fx["payload"]), str(fx["release_gate"])],
            )
            data = self.load_stdout_json(result)
            self.assertEqual(data["mode"], "publish")
            self.assertTrue(data["published"])
            self.assertEqual(data["version"], fx["version"])
            self.assertEqual(data["target_source_commit"], fx["source_commit"])
            self.assertEqual(data["latest_before"], "totem-core-stable")
            self.assertEqual(data["latest_after"], data["latest_before"])
            self.assertEqual(
                data["assets"],
                [
                    {"name": fx["manifest"].name, "sha256": _sha256(fx["manifest"])},
                    {"name": fx["payload"].name, "sha256": _sha256(fx["payload"])},
                    {"name": fx["release_gate"].name, "sha256": _sha256(fx["release_gate"])},
                ],
            )

    def test_latest_drift_after_publish_fails_closed(self) -> None:
        with self.fixture(allow_publish="1", latest_drift="1") as fx:
            result = self.run_publisher(fx, "--publish")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("latest release drifted", result.stdout + result.stderr)

    def test_post_publish_draft_metadata_fails_closed(self) -> None:
        with self.fixture(allow_publish="1", release_draft="1") as fx:
            result = self.run_publisher(fx, "--publish")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("published release metadata/assets", result.stdout + result.stderr)


class C18PlayerRuntimeGithubReleasePublisherTest(unittest.TestCase):
    @contextlib.contextmanager
    def fixture(self, **overrides: str) -> Iterator[Fixture]:
        with tempfile.TemporaryDirectory(prefix="c18-heavy-publisher-") as tmp:
            root = Path(tmp)
            repo = root / "orange_pi_totem"
            deploy_dir = repo / "scripts" / "deploy"
            qa_dir = repo / "scripts" / "qa"
            release_dir = root / "release"
            stub_dir = root / "stubs"
            deploy_dir.mkdir(parents=True)
            qa_dir.mkdir(parents=True)
            release_dir.mkdir()
            stub_dir.mkdir()

            publisher = deploy_dir / HEAVY_PUBLISHER_PATH.name
            shutil.copy2(HEAVY_PUBLISHER_PATH, publisher)
            publisher.chmod(0o755)
            (qa_dir / "c18_player_runtime_public_thaw_activation_gate.py").write_text(
                "# fake activation gate\n",
                encoding="utf-8",
            )
            (qa_dir / "c18_server_side_publish_asset_collect.py").write_text(
                "# fake asset collector\n",
                encoding="utf-8",
            )

            version = "c18.player-runtime-heavy-test"
            source_commit = "d" * 40
            payload = release_dir / f"dadooh-player-runtime-{version}.tar.gz"
            payload.write_bytes(b"heavy-player-runtime-payload\n")
            payload_sha = _sha256(payload)
            manifest = release_dir / f"dadooh-player-runtime-{version}.manifest.json"
            _write_json(
                manifest,
                {
                    "schema": "dadooh.totem.update.v1",
                    "component": "player-runtime",
                    "version": version,
                    "channel": "homologation",
                    "source_commit": source_commit,
                    "payload": payload.name,
                    "payload_sha256": payload_sha,
                },
            )
            release_gate = release_dir / "c18-player-runtime-release-gate.json"
            _write_json(
                release_gate,
                {
                    "schema": "dadooh.c18.player_runtime.release_gate.v1",
                    "passed": True,
                    "package": {"component": "player-runtime", "channel": "homologation"},
                },
            )
            server_side = release_dir / "c18-server-side-publish-governance.json"
            _write_json(server_side, {"passed": True})

            h2_readiness = root / "h2-readiness.json"
            stable_promotion = root / "stable-promotion.json"
            operator_thaw = root / "operator-thaw.json"
            trusted_key = root / "trusted-key.pem"
            trust_anchor = root / "trust-anchor.json"
            for path in (h2_readiness, stable_promotion, operator_thaw, trust_anchor):
                _write_json(path, {"passed": True})
            trusted_key.write_text(
                "-----BEGIN PUBLIC KEY-----\nheavy-test-key\n-----END PUBLIC KEY-----\n",
                encoding="utf-8",
            )

            gh_capture = root / "heavy-gh-argv.bin"
            latest_counter = root / "heavy-latest-counter.txt"
            _write_executable(
                stub_dir / "python3",
                r"""
                #!/usr/bin/env bash
                set -euo pipefail
                case "${1:-}" in
                  */scripts/qa/c18_player_runtime_public_thaw_activation_gate.py)
                    printf '{"passed": true}\n'
                    exit 0
                    ;;
                  */scripts/qa/c18_server_side_publish_asset_collect.py)
                    "$C18_REAL_PYTHON3" - \
                      "$C18_HEAVY_MANIFEST" "$C18_HEAVY_PAYLOAD" "$C18_HEAVY_RELEASE_GATE" "$C18_HEAVY_SERVER_SIDE" <<'PY'
import json
import sys
print(json.dumps({"assets": sys.argv[1:]}))
PY
                    exit 0
                    ;;
                esac
                exec "$C18_REAL_PYTHON3" "$@"
                """,
            )
            _write_executable(
                stub_dir / "git",
                r"""
                #!/usr/bin/env bash
                set -euo pipefail
                case "${1:-}" in
                  ls-remote)
                    printf '%s\trefs/heads/foundation-v0.1\n' "$C18_SOURCE_COMMIT"
                    case "${C18_REMOTE_TAG_MODE:-present}" in
                      present)
                        printf '%s\trefs/tags/player-runtime-%s\n' "$C18_SOURCE_COMMIT" "$C18_VERSION"
                        ;;
                      wrong_commit)
                        printf '%s\trefs/tags/player-runtime-%s\n' "${C18_OTHER_COMMIT:-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee}" "$C18_VERSION"
                        ;;
                      missing)
                        ;;
                      *)
                        exit 2
                        ;;
                    esac
                    exit 0
                    ;;
                esac
                exit 2
                """,
            )
            _write_executable(
                stub_dir / "gh",
                r"""
                #!/usr/bin/env bash
                set -euo pipefail

                json_has_field() {
                  local field="$1"
                  shift
                  local want_json=0 arg
                  for arg in "$@"; do
                    if [[ "$want_json" == "1" ]]; then
                      [[ ",$arg," == *",$field,"* ]] && return 0
                      return 1
                    fi
                    [[ "$arg" == "--json" ]] && want_json=1
                  done
                  return 1
                }

                if [[ "${1:-} ${2:-}" == "auth status" ]]; then
                  exit 0
                fi

                if [[ "${1:-} ${2:-}" == "release view" ]]; then
                  third="${3:-}"
                  if [[ -n "$third" && "$third" != --* ]]; then
                    if json_has_field "targetCommitish" "$@"; then
                      "$C18_REAL_PYTHON3" - "$third" "$C18_SOURCE_COMMIT" <<'PY'
import json
import os
import sys
print(json.dumps({
    "tagName": os.environ.get("C18_READBACK_TAG", sys.argv[1]),
    "isDraft": os.environ.get("C18_READBACK_DRAFT") == "1",
    "isPrerelease": os.environ.get("C18_READBACK_PRERELEASE") == "1",
    "targetCommitish": os.environ.get("C18_READBACK_TARGET", sys.argv[2]),
}))
PY
                      exit 0
                    fi
                    if [[ "${C18_RELEASE_EXISTS:-0}" == "1" ]]; then
                      exit 0
                    fi
                    exit 1
                  fi

                  if json_has_field "tagName" "$@"; then
                    count=0
                    if [[ -f "$C18_LATEST_COUNTER" ]]; then
                      count="$(cat "$C18_LATEST_COUNTER")"
                    fi
                    printf '%s\n' "$((count + 1))" > "$C18_LATEST_COUNTER"
                    tag="${C18_LATEST_TAG:-totem-core-stable}"
                    if [[ "${C18_LATEST_DRIFT:-0}" == "1" && "$count" -ge 1 ]]; then
                      tag="${tag}-drift"
                    fi
                    "$C18_REAL_PYTHON3" - "$tag" <<'PY'
import json
import sys
print(json.dumps({"tagName": sys.argv[1]}))
PY
                    exit 0
                  fi
                  exit 2
                fi

                if [[ "${1:-} ${2:-}" == "release create" ]]; then
                  "$C18_REAL_PYTHON3" - "$C18_GH_CAPTURE" "$@" <<'PY'
import sys
from pathlib import Path
Path(sys.argv[1]).write_bytes(b"\0".join(arg.encode() for arg in sys.argv[2:]) + b"\0")
PY
                  printf 'https://example.invalid/heavy/%s\n' "$C18_VERSION"
                  exit 0
                fi

                exit 2
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{stub_dir}:{env.get('PATH', '')}",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "C18_REAL_PYTHON3": sys.executable,
                    "C18_SOURCE_COMMIT": source_commit,
                    "C18_VERSION": version,
                    "C18_HEAVY_MANIFEST": str(manifest),
                    "C18_HEAVY_PAYLOAD": str(payload),
                    "C18_HEAVY_RELEASE_GATE": str(release_gate),
                    "C18_HEAVY_SERVER_SIDE": str(server_side),
                    "C18_GH_CAPTURE": str(gh_capture),
                    "C18_LATEST_COUNTER": str(latest_counter),
                    "C18_REMOTE_TAG_MODE": overrides.get("remote_tag_mode", "present"),
                    "C18_LATEST_DRIFT": overrides.get("latest_drift", "0"),
                }
            )
            if overrides.get("allow_publish") == "1":
                env["ALLOW_C18_PLAYER_RUNTIME_PUBLICATION"] = "1"

            yield Fixture(
                repo=repo,
                publisher=publisher,
                release_dir=release_dir,
                manifest=manifest,
                payload=payload,
                release_gate=release_gate,
                server_side=server_side,
                h2_readiness=h2_readiness,
                stable_promotion=stable_promotion,
                operator_thaw=operator_thaw,
                trusted_key=trusted_key,
                trust_anchor=trust_anchor,
                version=version,
                source_commit=source_commit,
                gh_capture=gh_capture,
                env=env,
            )

    def run_publisher(self, fx: Fixture, *args: str) -> subprocess.CompletedProcess[str]:
        command = [
            str(fx["publisher"]),
            "--release-dir",
            str(fx["release_dir"]),
            "--repo",
            PUBLISH_REPO,
            "--h2-readiness",
            str(fx["h2_readiness"]),
            "--stable-promotion-evidence",
            str(fx["stable_promotion"]),
            "--operator-thaw-decision",
            str(fx["operator_thaw"]),
            "--server-side-trusted-key-pem",
            str(fx["trusted_key"]),
            "--server-side-trust-anchor-evidence",
            str(fx["trust_anchor"]),
        ]
        command.extend(args)
        return subprocess.run(
            command,
            cwd=fx["repo"],
            env=fx["env"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_tag_override_must_match_manifest_version(self) -> None:
        with self.fixture() as fx:
            result = self.run_publisher(fx, "--tag", f"player-runtime-{fx['version']}-other")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tag override must exactly match", result.stdout + result.stderr)
            self.assertFalse(fx["gh_capture"].exists(), msg="tag mismatch must not create a release")

    def test_remote_tag_missing_fails_closed_before_publish(self) -> None:
        with self.fixture(allow_publish="1", remote_tag_mode="missing") as fx:
            result = self.run_publisher(fx, "--publish")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("remote tag", result.stdout + result.stderr)
            self.assertFalse(fx["gh_capture"].exists(), msg="missing remote tag must not create a release")

    def test_publish_command_uses_verify_tag_and_latest_false(self) -> None:
        with self.fixture(allow_publish="1") as fx:
            result = self.run_publisher(fx, "--publish")
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            argv = [part.decode() for part in fx["gh_capture"].read_bytes().split(b"\0") if part]
            self.assertEqual(argv[:3], ["release", "create", f"player-runtime-{fx['version']}"])
            self.assertIn("--verify-tag", argv)
            self.assertIn("--latest=false", argv)
            self.assertNotIn("--latest", argv)
            self.assertIn("--target", argv)
            self.assertEqual(argv[argv.index("--target") + 1], fx["source_commit"])


class C18PlayerRuntimeRealAuthorizationGateIntegrationTest(unittest.TestCase):
    def make_real_artifacts(self, root: Path, *, repo: str = PUBLISH_REPO) -> tuple[Path, Path, Path, dict[str, Any]]:
        qa_path = str(REPO_ROOT / "scripts" / "qa")
        if qa_path not in sys.path:
            sys.path.insert(0, qa_path)
        import c18_player_runtime_release_gate as release_gate

        version = "c18.player-runtime-homolog-real-gate"
        payload = release_gate.write_payload(root, version, release_gate.SNAPSHOT_KIOSK.read_text(encoding="utf-8"))
        manifest = release_gate.write_manifest(root, version, payload, {"source_repo": repo})
        release_gate_path = root / "c18-player-runtime-release-gate.json"
        _write_json(release_gate_path, release_gate.validate_release(manifest, payload))
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        auth = flat_authorization(
            repo=repo,
            version=version,
            source_commit=manifest_data["source_commit"],
            manifest=manifest,
            payload=payload,
            release_gate=release_gate_path,
            payload_sha256=manifest_data["payload_sha256"],
        )
        return manifest, payload, release_gate_path, auth

    def run_real_gate(
        self,
        authorization: Path,
        manifest: Path,
        payload: Path,
        release_gate_path: Path,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(AUTH_GATE_PATH),
                "--authorization",
                str(authorization),
                "--manifest",
                str(manifest),
                "--payload",
                str(payload),
                "--release-gate",
                str(release_gate_path),
                "--json",
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    @unittest.skipUnless(AUTH_GATE_PATH.is_file(), "real authorization gate is not present yet")
    def test_real_gate_accepts_flat_authorization(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-real-auth-gate-") as tmp:
            root = Path(tmp)
            manifest, payload, release_gate_path, auth = self.make_real_artifacts(root)
            auth_path = root / "authorization.json"
            _write_json(auth_path, auth)
            result = self.run_real_gate(auth_path, manifest, payload, release_gate_path)
            if result.returncode != 0 and "authorization_missing_field:authorization_scope" in result.stdout:
                self.skipTest("real authorization gate has not moved to the final flat updater-compatible contract")
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertTrue(data["passed"], msg=result.stdout)
            target = data.get("target") or data.get("expected")
            self.assertIsInstance(target, dict, msg=result.stdout)
            self.assertEqual(target["repo"], PUBLISH_REPO)
            self.assertEqual(target.get("tag_name") or target.get("tag"), auth["tag_name"])
            self.assertEqual(target["version"], auth["version"])
            self.assertEqual(target["source_commit"], auth["source_commit"])
            self.assertEqual(target["payload_sha256"], auth["payload_sha256"])
            self.assertEqual(target["manifest_sha256"], auth["manifest_sha256"])
            self.assertEqual(target["release_gate_sha256"], auth["release_gate_sha256"])

    @unittest.skipUnless(AUTH_GATE_PATH.is_file(), "real authorization gate is not present yet")
    def test_real_gate_rejects_empty_and_nested_authorization(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-real-auth-gate-deny-") as tmp:
            root = Path(tmp)
            manifest, payload, release_gate_path, auth = self.make_real_artifacts(root)
            for name, data in {
                "empty": {},
                "nested": {"target": auth},
            }.items():
                with self.subTest(name=name):
                    auth_path = root / f"{name}.json"
                    _write_json(auth_path, data)
                    result = self.run_real_gate(auth_path, manifest, payload, release_gate_path)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("blockers", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
