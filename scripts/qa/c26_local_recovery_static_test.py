#!/usr/bin/env python3
"""Static and executable contract checks for C26 local recovery."""

from __future__ import annotations

import json
import hashlib
import importlib.util
import os
import pathlib
import subprocess
import tarfile
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD_DIR = REPO_ROOT / "scripts" / "board"
FIRSTBOOT_UNIT = BOARD_DIR / "totem-firstboot-gate.service"
PRODUCT_RESET_GC_UNIT = BOARD_DIR / "totem-product-reset-gc.service"
FIRSTBOOT_SCRIPT = BOARD_DIR / "totem_firstboot_gate.sh"
SESSION_SCRIPT = BOARD_DIR / "totem_open_settings_session.sh"
TRIGGER_SCRIPT = BOARD_DIR / "totem_settings_trigger.py"
WRITER_SCRIPT = BOARD_DIR / "totem_config_writer_real.py"
CLEANUP_SCRIPT = BOARD_DIR / "totem_open_settings_cleanup.sh"
UPDATECTL_SCRIPT = BOARD_DIR / "totem_updatectl.py"
IMAGE_EMBED = REPO_ROOT / "scripts" / "build" / "totem_core_image_embed.py"
PACKAGE_BUILDER = REPO_ROOT / "scripts" / "deploy" / "build_totem_core_release_package.sh"


def function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index(f"\n{next_name}() {{", start)
    return source[start:end]


def load_updatectl(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, UPDATECTL_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class C26LocalRecoveryContractTest(unittest.TestCase):
    def test_reopening_settings_preserves_device_token_identity_privately(self) -> None:
        session = SESSION_SCRIPT.read_text(encoding="utf-8")
        active_config_copy = function_body(
            session,
            "prepare_private_values_from_active_config_if_requested",
            "validate_private_values_metadata",
        )
        self.assertIn(
            'for field in ("api_url", "api_key", "station_id", "api_token_id"):',
            active_config_copy,
        )
        self.assertIn('tmp.write_text(json.dumps(payload, indent=2, sort_keys=True)', active_config_copy)
        self.assertNotIn("print(payload", active_config_copy)

    def test_firstboot_orders_recovery_before_both_ota_agents(self) -> None:
        unit = FIRSTBOOT_UNIT.read_text(encoding="utf-8")
        before = next(line for line in unit.splitlines() if line.startswith("Before="))
        before_units = set(before.removeprefix("Before=").split())
        self.assertIn("totem-update-agent.service", before_units)
        self.assertIn("totem-player-runtime-update-agent.service", before_units)

        embed = IMAGE_EMBED.read_text(encoding="utf-8")
        self.assertIn('"totem-firstboot-gate.service"', embed)
        self.assertIn('"/etc/systemd/system/totem-firstboot-gate.service"', embed)
        self.assertIn("_dump_sha256(rootfs, target)", embed)
        self.assertIn('"product-reset-v1"', embed)
        self.assertIn("FIRSTBOOT_GATE_SERVICE_WANTS", embed)
        self.assertIn("firstboot_gate_enabled_symlink_target_exact", embed)
        self.assertIn("product_reset_gc_pulled_by_player", embed)
        self.assertIn("product_reset_gc_unit_installed_exact", embed)
        self.assertIn("product_reset_gc_unit_static", embed)
        self.assertIn("product_reset_gc_player_dropin_installed_exact", embed)

    def test_bulk_cleanup_is_exact_and_deferred_until_after_player_restore(self) -> None:
        writer = WRITER_SCRIPT.read_text(encoding="utf-8")
        finalize = writer[
            writer.index("def product_reset_finalize(") : writer.index(
                "\ndef product_reset_complete_onboarding(", writer.index("def product_reset_finalize(")
            )
        ]
        completion = writer[
            writer.index("def product_reset_complete_onboarding(") : writer.index(
                "\ndef product_reset_validate_new_onboarding_config(",
                writer.index("def product_reset_complete_onboarding("),
            )
        ]
        gc = writer[
            writer.index("def product_reset_gc(") : writer.index(
                "\ndef product_reset_cli_exit_code(", writer.index("def product_reset_gc(")
            )
        ]
        self.assertNotIn("product_reset_remove_graveyard", finalize)
        self.assertNotIn("product_reset_remove_graveyard", completion)
        self.assertIn("product_reset_queue_gc", completion)
        self.assertIn("product_reset_load_gc_pending", gc)
        self.assertIn("product_reset_remove_graveyard(ctx, operation_id)", gc)
        self.assertLess(
            gc.index("product_reset_remove_graveyard(ctx, operation_id)"),
            gc.index('product_reset_unlink_private_file(product_reset_gc_pending_path(ctx), "gc-pending")'),
        )
        remove_graveyard = writer[
            writer.index("def product_reset_remove_graveyard(") : writer.index(
                "\ndef product_reset_prepare_graveyard_parent(",
                writer.index("def product_reset_remove_graveyard("),
            )
        ]
        sanitize_config = writer[
            writer.index("def product_reset_sanitize_graveyard_config(") : writer.index(
                "\ndef product_reset_recreate_domain(",
                writer.index("def product_reset_sanitize_graveyard_config("),
            )
        ]
        for body in (remove_graveyard, sanitize_config):
            self.assertLess(body.index("product_reset_require_no_mounts_below"), body.index("shutil.rmtree("))

        unit = PRODUCT_RESET_GC_UNIT.read_text(encoding="utf-8")
        self.assertIn("After=kiosky-player.service", unit)
        self.assertIn("ConditionPathExists=/data/state/totem-appliance/product-reset/gc-pending.json", unit)
        self.assertIn("Nice=19", unit)
        self.assertIn("IOSchedulingClass=best-effort", unit)
        self.assertIn("IOSchedulingPriority=7", unit)
        self.assertIn("--product-reset-gc-max 1", unit)
        self.assertNotIn("WantedBy=multi-user.target", unit)

        player_dropin = (
            BOARD_DIR / "systemd" / "kiosky-player.service.d" / "20-dadooh-launcher.conf"
        ).read_text(encoding="utf-8")
        self.assertIn("Wants=totem-product-reset-gc.service", player_dropin)

        cleanup = CLEANUP_SCRIPT.read_text(encoding="utf-8")
        normal = cleanup[cleanup.index('rm -f "$REQUEST_DIR/request.json"') :]
        self.assertLess(normal.index("restore_product_state || true"), normal.index("enqueue_product_reset_gc || true"))

        session = SESSION_SCRIPT.read_text(encoding="utf-8")
        pending_check = function_body(session, "product_reset_cleanup_pending", "remove_session_lock_if_safe")
        with tempfile.TemporaryDirectory(prefix="dadooh-c26-ui-gc-guard-", dir="/tmp") as raw_root:
            state = pathlib.Path(raw_root) / "state"
            env = dict(os.environ)
            env["PRODUCT_RESET_STATE_DIR"] = str(state)

            def pending() -> bool:
                return (
                    subprocess.run(
                        ["bash", "-c", pending_check + "\nproduct_reset_cleanup_pending"],
                        env=env,
                        check=False,
                        timeout=10,
                    ).returncode
                    == 0
                )

            self.assertFalse(pending())
            (state / "graveyard").mkdir(parents=True, mode=0o700)
            self.assertFalse(pending())
            (state / "graveyard" / "11111111-2222-4333-8444-555555555555").mkdir(mode=0o700)
            self.assertTrue(pending())

    def test_ota_stays_blocked_until_deferred_cleanup_finishes(self) -> None:
        updatectl = load_updatectl("c26_updatectl_guard")

        with tempfile.TemporaryDirectory(prefix="dadooh-c26-update-guard-", dir="/tmp") as raw_root:
            root = pathlib.Path(raw_root)
            settings_lock = root / "settings-lock"
            settings_request = root / "request.json"
            gc_pending = root / "gc-pending.json"
            graveyard = root / "graveyard"
            updatectl.COMPONENT = "totem-core"
            updatectl.SETTINGS_LOCK = settings_lock
            updatectl.SETTINGS_REQUEST_FILE = settings_request
            updatectl.PRODUCT_RESET_GC_PENDING_FILE = gc_pending
            updatectl.PRODUCT_RESET_GRAVEYARD_DIR = graveyard
            updatectl._systemd_unit_state = lambda _unit: "inactive"

            self.assertEqual(updatectl._component_apply_guard(), (True, "settings_session_inactive"))
            gc_pending.write_text("{}\n", encoding="utf-8")
            gc_pending.chmod(0o600)
            self.assertEqual(updatectl._component_apply_guard(), (False, "product_reset_gc_pending"))
            gc_pending.unlink()

            graveyard.mkdir(mode=0o700)
            self.assertEqual(updatectl._component_apply_guard(), (True, "settings_session_inactive"))
            (graveyard / "11111111-2222-4333-8444-555555555555").mkdir(mode=0o700)
            self.assertEqual(updatectl._component_apply_guard(), (False, "product_reset_graveyard_present"))

    def test_c26a_and_c26b_package_identities_cannot_collide(self) -> None:
        common = [
            str(PACKAGE_BUILDER),
            "--prepare-only",
            "--allow-dirty",
            "--channel=homologation",
            "--version=c26-identity-contract",
        ]
        c26a = subprocess.run(
            common,
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
        c26b = subprocess.run(
            [*common, "--enable-totem-actions"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
        self.assertIn("version         = c26-identity-contract\n", c26a)
        self.assertIn("version         = c26-identity-contract-actions\n", c26b)
        self.assertNotEqual(c26a, c26b)
        collision = subprocess.run(
            [
                str(PACKAGE_BUILDER),
                "--prepare-only",
                "--allow-dirty",
                "--channel=homologation",
                "--version=c26-identity-contract-actions",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(collision.returncode, 0)
        self.assertIn("suffix -actions is reserved", collision.stderr)

    def test_actions_remain_hidden_until_loaded_boot_graph_is_safe(self) -> None:
        session = SESSION_SCRIPT.read_text(encoding="utf-8")
        boot_gate = function_body(session, "totem_actions_boot_order_safe", "totem_core_actions_capable")
        capability = function_body(session, "totem_core_actions_capable", "consume_totem_action_request")
        self.assertIn('"LoadState": "loaded"', boot_gate)
        self.assertIn('"UnitFileState": "enabled"', boot_gate)
        self.assertIn('"ActiveState": "inactive"', boot_gate)
        self.assertIn('"Result": "success"', boot_gate)
        self.assertIn('"ExecMainStatus": "0"', boot_gate)
        self.assertIn("dadooh.c26.firstboot-ready.v1", boot_gate)
        self.assertIn("/proc/sys/kernel/random/boot_id", boot_gate)
        self.assertIn('"totem-update-agent.service"', boot_gate)
        self.assertIn('"totem-player-runtime-update-agent.service"', boot_gate)
        self.assertIn("totem_actions_boot_order_safe", capability)
        self.assertIn("totem_actions_image_contract_safe", capability)
        self.assertIn("check-image-contract", session)
        self.assertIn("c26-product-reset-gc-static-v1", session)
        self.assertIn('TOTEM_ACTIONS_AVAILABLE="0"', session)

    def test_actions_require_exact_static_gc_image_contract(self) -> None:
        updatectl = load_updatectl("c26_updatectl_image_contract")
        expected_bytes = PRODUCT_RESET_GC_UNIT.read_bytes()
        expected_hash = hashlib.sha256(expected_bytes).hexdigest()
        self.assertEqual(expected_hash, updatectl.PRODUCT_RESET_GC_UNIT_SHA256)

        with tempfile.TemporaryDirectory(prefix="dadooh-c26-image-contract-", dir="/tmp") as raw_root:
            root = pathlib.Path(raw_root)
            unit_path = root / "totem-product-reset-gc.service"
            unit_path.write_bytes(expected_bytes)
            unit_path.chmod(0o644)
            gc_properties = {
                "LoadState": "loaded",
                "UnitFileState": "static",
                "FragmentPath": str(unit_path),
                "NeedDaemonReload": "no",
                "Type": "oneshot",
                "After": "kiosky-player.service",
            }
            player_properties = {
                "LoadState": "loaded",
                "Wants": "totem-product-reset-gc.service network-online.target",
            }

            def runner(*args: str) -> subprocess.CompletedProcess:
                unit = args[1]
                properties = gc_properties if unit == "totem-product-reset-gc.service" else player_properties
                requested = [arg.removeprefix("--property=") for arg in args[2:]]
                stdout = "".join(f"{name}={properties.get(name, '')}\n" for name in requested)
                return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

            def check() -> tuple[bool, str]:
                return updatectl._totem_actions_image_contract_check(
                    gc_unit_path=unit_path,
                    expected_unit_sha256=expected_hash,
                    expected_uid=os.getuid(),
                    expected_gid=os.getgid(),
                    systemctl_runner=runner,
                )

            self.assertEqual(check(), (True, "c26_product_reset_gc_image_contract_ok"))
            for name, target, key, bad_value in (
                ("not-static", gc_properties, "UnitFileState", "enabled"),
                ("daemon-reload-needed", gc_properties, "NeedDaemonReload", "yes"),
                ("wrong-fragment", gc_properties, "FragmentPath", "/etc/systemd/system/other.service"),
                ("missing-wants", player_properties, "Wants", "network-online.target"),
            ):
                with self.subTest(name=name):
                    original = target[key]
                    target[key] = bad_value
                    self.assertFalse(check()[0])
                    target[key] = original

            unit_path.write_text("[Service]\nType=oneshot\n", encoding="utf-8")
            unit_path.chmod(0o644)
            self.assertEqual(check(), (False, "product_reset_gc_unit_hash_mismatch"))
            unit_path.unlink()
            self.assertEqual(check(), (False, "product_reset_gc_unit_missing"))

    def test_actions_shell_consumes_fixed_updater_image_probe(self) -> None:
        session = SESSION_SCRIPT.read_text(encoding="utf-8")
        image_gate = function_body(
            session,
            "totem_actions_image_contract_safe",
            "totem_core_actions_capable",
        )
        with tempfile.TemporaryDirectory(prefix="dadooh-c26-image-probe-cli-", dir="/tmp") as raw_root:
            root = pathlib.Path(raw_root)
            mock_updatectl = root / "totem-updatectl"
            mock_updatectl.write_text('#!/bin/sh\nexit "${TOTEM_C26_TEST_IMAGE_RC:-1}"\n', encoding="utf-8")
            mock_updatectl.chmod(0o700)
            env = dict(os.environ)
            env.update(
                {
                    "TOTEM_C26_TEST_MODE": "1",
                    "TOTEM_C26_TEST_UPDATECTL_BIN": str(mock_updatectl),
                    "TOTEM_C26_TEST_IMAGE_RC": "0",
                }
            )
            command = ["bash", "-c", image_gate + "\ntotem_actions_image_contract_safe"]
            self.assertEqual(subprocess.run(command, env=env, check=False).returncode, 0)
            env["TOTEM_C26_TEST_IMAGE_RC"] = "1"
            self.assertNotEqual(subprocess.run(command, env=env, check=False).returncode, 0)

    def test_actions_require_success_for_the_current_boot(self) -> None:
        session = SESSION_SCRIPT.read_text(encoding="utf-8")
        boot_gate = function_body(session, "totem_actions_boot_order_safe", "totem_core_actions_capable")
        good_boot_id = "11111111-2222-4333-8444-555555555555"
        properties = {
            "LoadState": "loaded",
            "UnitFileState": "enabled",
            "ActiveState": "inactive",
            "SubState": "dead",
            "Result": "success",
            "ExecMainStatus": "0",
            "Before": "totem-update-agent.service totem-player-runtime-update-agent.service",
        }

        with tempfile.TemporaryDirectory(prefix="dadooh-c26-boot-ready-", dir="/tmp") as raw_root:
            root = pathlib.Path(raw_root)
            mock_systemctl = root / "systemctl"
            output = root / "systemctl-output"
            boot_id_file = root / "boot-id"
            marker = root / "c26-firstboot-ready.json"
            mock_systemctl.write_text('#!/bin/sh\ncat "$TOTEM_C26_TEST_SYSTEMCTL_OUTPUT"\n', encoding="utf-8")
            mock_systemctl.chmod(0o700)
            boot_id_file.write_text(good_boot_id + "\n", encoding="ascii")

            env = dict(os.environ)
            env.update(
                {
                    "TOTEM_C26_TEST_MODE": "1",
                    "TOTEM_C26_TEST_SYSTEMCTL_BIN": str(mock_systemctl),
                    "TOTEM_C26_TEST_SYSTEMCTL_OUTPUT": str(output),
                    "TOTEM_C26_TEST_READY_MARKER": str(marker),
                    "TOTEM_C26_TEST_BOOT_ID_FILE": str(boot_id_file),
                }
            )

            def write_properties(overrides: dict[str, str] | None = None) -> None:
                current = dict(properties)
                current.update(overrides or {})
                output.write_text(
                    "".join(f"{key}={value}\n" for key, value in current.items()),
                    encoding="utf-8",
                )

            def write_marker(boot_id: str = good_boot_id) -> None:
                marker.write_text(
                    json.dumps(
                        {
                            "schema_version": "dadooh.c26.firstboot-ready.v1",
                            "boot_id": boot_id,
                            "completed_at_utc": "2026-07-17T12:00:00Z",
                        },
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                marker.chmod(0o600)

            def run_gate() -> int:
                return subprocess.run(
                    ["bash", "-c", boot_gate + "\ntotem_actions_boot_order_safe"],
                    env=env,
                    check=False,
                    timeout=15,
                ).returncode

            write_properties()
            write_marker()
            self.assertEqual(run_gate(), 0, "healthy current boot should expose actions")

            cases = (
                ("disabled", {"UnitFileState": "disabled"}, True, good_boot_id),
                ("failed", {"Result": "exit-code", "ExecMainStatus": "1"}, True, good_boot_id),
                ("still-activating", {"ActiveState": "activating", "SubState": "start"}, True, good_boot_id),
                ("missing-marker", {}, False, good_boot_id),
                ("old-boot-marker", {}, True, "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"),
            )
            for name, overrides, marker_present, marker_boot_id in cases:
                with self.subTest(name=name):
                    write_properties(overrides)
                    if marker_present:
                        write_marker(marker_boot_id)
                    else:
                        marker.unlink(missing_ok=True)
                    self.assertNotEqual(run_gate(), 0)

    def test_firstboot_guard_precedes_update_lock_and_player_stop(self) -> None:
        script = FIRSTBOOT_SCRIPT.read_text(encoding="utf-8")
        reconcile = function_body(script, "reconcile_product_reset", "c17_4_trace")
        ordered = [
            "ensure_product_reset_guard_lock",
            "write_product_reset_resume_request",
            "acquire_product_reset_update_lock",
            "stop_player_for_product_reset",
            "resume_product_reset_local",
        ]
        offsets = [reconcile.index(token) for token in ordered]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("complete_product_reset_onboarding_if_configured", reconcile)
        self.assertLess(
            script.index('c17_4_trace "firstboot_gate_complete"'),
            script.rindex("write_firstboot_ready_marker"),
        )

    def test_terminal_actions_are_reconciled_in_two_phases(self) -> None:
        session = SESSION_SCRIPT.read_text(encoding="utf-8")
        writer = function_body(session, "write_terminal_action_marker", "schedule_terminal_action_reconcile")
        reconcile = function_body(
            session,
            "schedule_terminal_action_reconcile",
            "cancel_terminal_action_reconcile",
        )
        self.assertIn("/usr/bin/systemd-run", reconcile)
        self.assertIn("--property=DefaultDependencies=no", reconcile)
        self.assertIn("--on-active=125s", reconcile)
        self.assertIn("--on-unit-active=30s", reconcile)
        self.assertIn("--timer-property=DefaultDependencies=no", reconcile)
        self.assertIn("--expire-terminal-action", reconcile)
        self.assertIn("--terminal-action-reconcile-unit", reconcile)
        self.assertIn("/opt/totem/bin/totem_open_settings_cleanup.sh", reconcile)
        action_start = session.index("    restart|poweroff)")
        action_block = session[action_start : session.index("    product_reset)", action_start)]
        prepared_index = action_block.index('write_terminal_action_marker "prepared"')
        reconcile_index = action_block.index('schedule_terminal_action_reconcile "$requested_action_id"')
        systemctl_index = action_block.index('/usr/bin/systemctl --no-block')
        accepted_index = action_block.index('write_terminal_action_marker "accepted"')
        pending_index = action_block.index('TERMINAL_ACTION_PENDING="true"')
        self.assertEqual(
            [prepared_index, reconcile_index, systemctl_index, accepted_index, pending_index],
            sorted([prepared_index, reconcile_index, systemctl_index, accepted_index, pending_index]),
        )
        self.assertIn("totem_terminal_action_reconcile_schedule_failed", action_block)
        self.assertGreaterEqual(action_block.count("cancel_terminal_action_reconcile"), 2)

        cleanup = CLEANUP_SCRIPT.read_text(encoding="utf-8")
        complete_start = cleanup.index("terminal_action_reconcile_complete() {")
        stop_start = cleanup.index("stop_terminal_action_reconcile() {", complete_start)
        complete_check = cleanup[complete_start:stop_start]
        self.assertIn('EXPIRE_TERMINAL_ACTION" = "true', complete_check)
        self.assertIn('[ "$PLAYER_RESTORE_START_RC" = "0" ]', complete_check)
        self.assertNotIn("not_attempted", complete_check)
        restore = function_body(cleanup, "restore_product_state", "enqueue_product_reset_gc")
        self.assertLess(
            restore.index("systemctl is-active --quiet kiosky-player.service"),
            restore.index("systemctl is-enabled kiosky-player.service"),
        )
        self.assertIn('PLAYER_RESTORE_START_MODE="already-active"', restore)
        self.assertIn('PLAYER_RESTORE_START_MODE="service-not-enabled"', restore)
        self.assertIn('PLAYER_RESTORE_START_RC="1"', restore)
        normal_cleanup = cleanup[cleanup.index('rm -f "$REQUEST_DIR/request.json"') :]
        restore_index = normal_cleanup.index("restore_product_state")
        status_index = normal_cleanup.index("write_status false")
        stop_index = normal_cleanup.index("stop_terminal_action_reconcile")
        self.assertEqual(
            [restore_index, status_index, stop_index],
            sorted([restore_index, status_index, stop_index]),
        )
        self.assertNotIn(
            "stop_terminal_action_reconcile",
            cleanup[cleanup.index("if session_process_running; then") : cleanup.index('rm -f "$REQUEST_DIR/request.json"')],
        )
        cleanup_start = cleanup.index("terminal_action_pending() {")
        cleanup_end = cleanup.index("\nif terminal_action_pending; then", cleanup_start)
        pending_check = cleanup[cleanup_start:cleanup_end]
        request_id = "11111111-2222-4333-8444-555555555555"
        other_request_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

        with tempfile.TemporaryDirectory(prefix="dadooh-c26-terminal-action-", dir="/tmp") as raw_root:
            root = pathlib.Path(raw_root)
            marker = root / "terminal-action.json"
            env = dict(os.environ)
            env.update(
                {
                    "TERMINAL_ACTION_MARKER": str(marker),
                    "SETTINGS_SESSION_ID": "1" * 32,
                    "TERMINAL_ACTION_MAX_AGE_SEC": "120",
                    "EXPIRE_TERMINAL_ACTION": "false",
                }
            )

            def run_shell(command: str) -> int:
                return subprocess.run(
                    ["bash", "-c", writer + "\n" + pending_check + "\n" + command],
                    env=env,
                    check=False,
                    timeout=15,
                ).returncode

            self.assertEqual(
                run_shell(f'write_terminal_action_marker prepared restart "{request_id}"'),
                0,
            )
            self.assertNotEqual(
                run_shell("terminal_action_pending"),
                0,
                "a cut before systemctl acceptance must not preserve locks",
            )
            self.assertNotEqual(
                run_shell(f'write_terminal_action_marker accepted restart "{other_request_id}"'),
                0,
                "acceptance must match the exact prepared request",
            )
            self.assertEqual(
                run_shell(f'write_terminal_action_marker accepted restart "{request_id}"'),
                0,
            )
            self.assertEqual(
                run_shell("terminal_action_pending"),
                0,
                "a fresh accepted action may preserve locks during shutdown",
            )
            self.assertNotEqual(
                run_shell("EXPIRE_TERMINAL_ACTION=true; terminal_action_pending"),
                0,
                "the delayed reconciler must force normal cleanup after the deadline",
            )

            payload = json.loads(marker.read_text(encoding="utf-8"))
            payload["accepted_at_utc"] = "2020-01-01T00:00:00Z"
            marker.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            marker.chmod(0o600)
            self.assertNotEqual(
                run_shell("terminal_action_pending"),
                0,
                "a stale accepted action must restore the normal cleanup path",
            )

            restore_probe = (
                restore
                + "\n"
                + complete_check
                + r'''
systemctl() {
  case "$1:$FAKE_PLAYER_STATE" in
    is-active:active) return 0 ;;
    is-active:*) return 3 ;;
    is-enabled:enabled) return 0 ;;
    is-enabled:*) return 1 ;;
    *) return 1 ;;
  esac
}
show_transition() { :; }
PLAYER_RESTORE_ATTEMPTED=false
PLAYER_RESTORE_START_MODE=none
PLAYER_RESTORE_START_RC=not_attempted
EXPIRE_TERMINAL_ACTION=true
TERMINAL_ACTION_RECONCILE_UNIT=totem-terminal-action-reconcile-11111111222243338444555555555555
REQUEST_DIR="$TEST_ROOT"
LOCK_DIR="$TEST_ROOT/missing-lock"
TERMINAL_ACTION_MARKER="$TEST_ROOT/missing-marker"
restore_product_state || true
printf '%s|%s\n' "$PLAYER_RESTORE_START_MODE" "$PLAYER_RESTORE_START_RC"
terminal_action_reconcile_complete
'''
            )

            def run_restore_probe(state: str) -> subprocess.CompletedProcess[str]:
                probe_env = dict(os.environ)
                probe_env.update({"FAKE_PLAYER_STATE": state, "TEST_ROOT": str(root)})
                return subprocess.run(
                    ["bash", "-c", restore_probe],
                    env=probe_env,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

            active = run_restore_probe("active")
            self.assertEqual(active.returncode, 0)
            self.assertIn("already-active|0", active.stdout)
            disabled = run_restore_probe("disabled")
            self.assertNotEqual(disabled.returncode, 0)
            self.assertIn("service-not-enabled|1", disabled.stdout)

    def test_persistent_reset_can_recreate_its_runtime_request(self) -> None:
        trigger = TRIGGER_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('write_request(request_dir, "product_reset_resume")', trigger)
        self.assertIn('product_reset_automatic_resume_action("revocation", None, "retryable") == "retry"', trigger)
        subprocess.run(["python3", str(TRIGGER_SCRIPT), "--self-test"], check=True)

    def test_completion_requires_a_valid_new_config_and_full_companion_health(self) -> None:
        writer = WRITER_SCRIPT.read_text(encoding="utf-8")
        completion = writer[
            writer.index("def product_reset_complete_onboarding(") : writer.index(
                "\ndef product_reset_gc(", writer.index("def product_reset_complete_onboarding(")
            )
        ]
        self.assertIn("product_reset_validate_new_onboarding_config", completion)
        updatectl = UPDATECTL_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('if "product-reset-v1" in declared_capabilities:', updatectl)
        for declaration in (
            "python3 bin/totem_config_writer_real.py --self-test",
            "python3 bin/totem_settings_trigger.py --self-test",
            "bash bin/totem_firstboot_gate.sh --self-test",
            "bash bin/totem_open_settings_cleanup.sh --self-test",
        ):
            self.assertGreaterEqual(updatectl.count(declaration), 2)

        commands = (
            ["python3", str(WRITER_SCRIPT), "--self-test"],
            ["python3", str(TRIGGER_SCRIPT), "--self-test"],
            ["bash", str(FIRSTBOOT_SCRIPT), "--self-test"],
            ["bash", str(CLEANUP_SCRIPT), "--self-test"],
        )
        for command in commands:
            subprocess.run(command, check=True, timeout=45)

    def test_actions_package_requires_image_feature_and_health_gate(self) -> None:
        updatectl = load_updatectl("c26_updatectl_package_gate")
        with tempfile.TemporaryDirectory(prefix="dadooh-c26-package-gate-", dir="/tmp") as raw_root:
            root = pathlib.Path(raw_root)
            common = [
                str(PACKAGE_BUILDER),
                "--build-package",
                "--allow-dirty",
                "--channel=homologation",
                f"--out-base={root}",
            ]
            subprocess.run([*common, "--version=c26-package-a"], cwd=REPO_ROOT, check=True, timeout=60)
            subprocess.run(
                [*common, "--version=c26-package-b", "--enable-totem-actions"],
                cwd=REPO_ROOT,
                check=True,
                timeout=60,
            )
            a_dir = root / "c26-package-a"
            b_dir = root / "c26-package-b-actions"
            a_manifest = json.loads(next(a_dir.glob("*.manifest.json")).read_text(encoding="utf-8"))
            b_manifest = json.loads(next(b_dir.glob("*.manifest.json")).read_text(encoding="utf-8"))
            feature = "c26-product-reset-gc-static-v1"
            self.assertNotIn(feature, a_manifest["requires"]["updater_features"])
            self.assertIn(feature, b_manifest["requires"]["updater_features"])

            payload = next(b_dir.glob("*.tar.gz"))
            release = root / "extracted-actions"
            release.mkdir()
            with tarfile.open(payload, "r:gz") as archive:
                archive.extractall(release, filter="data")
            health = json.loads((release / "health/totem-core-health.json").read_text(encoding="utf-8"))
            self.assertIn("totem-actions-v1", health["capabilities"])

            policy = {
                "schema": "dadooh.totem.update.policy.v1",
                "device_channel": "homologation",
                "device_track": "c18-hwdecode",
                "allowed_components": ["totem-core"],
                "allow_prerelease": True,
                "allow_downgrade": False,
            }
            original_probe = updatectl._totem_actions_image_contract_check
            original_health_cmd = updatectl._run_health_cmd
            original_restore_check = updatectl._restore_order_static_check
            try:
                updatectl._totem_actions_image_contract_check = lambda: (False, "old_image")
                with self.assertRaisesRegex(RuntimeError, "totem actions image contract not met"):
                    updatectl._validate_manifest(b_manifest, policy=policy, component="totem-core")
                updatectl._totem_actions_image_contract_check = lambda: (True, "ok")
                updatectl._validate_manifest(b_manifest, policy=policy, component="totem-core")

                updatectl._run_health_cmd = lambda _args, timeout_s=45: (True, "ok")
                updatectl._restore_order_static_check = lambda _bin: (True, "ok")
                updatectl._totem_actions_image_contract_check = lambda: (False, "wiring_wrong")
                self.assertEqual(
                    updatectl._totem_core_health_check(release),
                    (False, "totem_actions_image_contract:wiring_wrong"),
                )
                updatectl._totem_actions_image_contract_check = lambda: (True, "ok")
                self.assertTrue(updatectl._totem_core_health_check(release)[0])
            finally:
                updatectl._totem_actions_image_contract_check = original_probe
                updatectl._run_health_cmd = original_health_cmd
                updatectl._restore_order_static_check = original_restore_check

    def test_homologation_seed_tombstone_blocks_reintroduction(self) -> None:
        session = SESSION_SCRIPT.read_text(encoding="utf-8")
        seed_gate = function_body(
            session,
            "product_reset_homologation_seed_disabled_safe",
            "remove_session_lock_if_safe",
        )
        with tempfile.TemporaryDirectory(prefix="dadooh-c26-seed-tombstone-", dir="/tmp") as raw_root:
            root = pathlib.Path(raw_root)
            state = root / "product-reset"
            state.mkdir(mode=0o700)
            marker = state / "homologation-seed-disabled.json"
            marker.write_text(
                json.dumps(
                    {
                        "schema_version": "dadooh-c26a-product-reset.v1",
                        "disabled": True,
                        "disabled_at_utc": "2026-07-17T12:00:00Z",
                        "first_operation_id": "11111111-2222-4333-8444-555555555555",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            marker.chmod(0o600)
            seed = root / "private-values.seed.json"
            env = dict(os.environ)
            env.update(
                {
                    "TOTEM_C26_TEST_MODE": "1",
                    "PRODUCT_RESET_STATE_DIR": str(state),
                    "TOTEM_C26_TEST_HOMOLOGATION_SEED": str(seed),
                }
            )
            command = ["bash", "-c", seed_gate + "\nproduct_reset_homologation_seed_disabled_safe"]
            self.assertEqual(subprocess.run(command, env=env, check=False).returncode, 0)
            seed.write_text('{"api_key":"must-not-be-read"}\n', encoding="utf-8")
            seed.chmod(0o600)
            self.assertNotEqual(subprocess.run(command, env=env, check=False).returncode, 0)
            seed.unlink()
            marker.write_text("{}\n", encoding="utf-8")
            marker.chmod(0o600)
            self.assertNotEqual(subprocess.run(command, env=env, check=False).returncode, 0)

    def test_extended_product_reset_fault_matrix(self) -> None:
        subprocess.run(
            ["python3", str(WRITER_SCRIPT), "--extended-self-test"],
            check=True,
            timeout=240,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
