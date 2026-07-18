#!/usr/bin/env python3
"""Static and executable contract checks for C26 local recovery."""

from __future__ import annotations

import json
import hashlib
import importlib.util
import os
import pathlib
import shlex
import subprocess
import sys
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

if str(BOARD_DIR) not in sys.path:
    sys.path.insert(0, str(BOARD_DIR))

import totem_api_url_contract as api_contract
import totem_config_contract_validate as config_contract
import totem_config_writer_real as config_writer
import totem_qr_pairing_client as pairing_client


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
    def test_api_transport_contract_is_compositional_before_reset(self) -> None:
        invalid_urls = (
            "https://api.example.com:",
            "https://[2001:db8::1",
            "https://%/search",
            "https://a..example.com/search",
            "https://" + ("a" * 64) + ".example.com/search",
            "https://api.example.com\\bad/search",
            "https://api.example.com/nao-ascii-é",
        )
        for value in invalid_urls:
            with self.assertRaises(api_contract.ApiUrlContractError):
                api_contract.validate_https_api_url(value)
            with self.assertRaises(config_writer.WriterError):
                config_writer.product_reset_validate_https_api_url(value)
            with self.assertRaises(pairing_client.PairingError):
                pairing_client.validate_api_url(value)

            candidate = config_contract.build_mock_candidate()
            candidate["api_url"] = value
            status = config_contract.validate_candidate_config(candidate, "real-dry-run")
            self.assertFalse(status["valid"])
            self.assertTrue(
                any(item["field"] == "api_url" for item in status["invalid_fields"]),
                value,
            )

        invalid_keys = (
            "A" * 15,
            "A" * 4097,
            "é" * 1500,
            "😀" * 16,
            ("A" * 16) + "\n",
        )
        for value in invalid_keys:
            with self.assertRaises(api_contract.ApiKeyContractError):
                api_contract.validate_api_key_format(value)
            with self.assertRaises(config_writer.WriterError):
                config_writer.product_reset_validate_api_key(value)
            with self.assertRaises(pairing_client.PairingError):
                pairing_client.validate_api_key(value)

        self.assertEqual(
            pairing_client.PRODUCT_RESET_MAX_CREDENTIAL_BYTES,
            api_contract.MAX_PRODUCT_RESET_CREDENTIAL_BYTES,
        )

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

    def test_openvt_exec_transport_preserves_semantic_exit_codes_fail_closed(self) -> None:
        session = SESSION_SCRIPT.read_text(encoding="utf-8")
        launch = (
            '/usr/bin/setsid --wait /usr/bin/openvt -c "$REMOTE_TTY" '
            '-s -f -e -- \\\n'
            '    /usr/bin/env TERM=linux'
        )
        self.assertEqual(session.count(launch), 2)
        self.assertNotIn("-f -w --", session)
        self.assertNotIn("normalize_openvt_semantic_exit", session)
        self.assertNotIn("RAW_WIZARD_RC", session)

        launch_start = session.index('c15_trace "before_openvt"')
        wait_for_child = session.index('\n    wait "$OPENVT_PID"\n    WIZARD_RC="$?"', launch_start)
        recovery_branch = session.index('if [ "$WIZARD_RC" = "76" ]')
        action_branch = session.index('elif [ "$WIZARD_RC" = "75" ]')
        action_without_exit = session.index(
            'elif [ -e "$ACTION_REQUEST_FILE" ] || [ -L "$ACTION_REQUEST_FILE" ]; then'
        )
        self.assertLess(wait_for_child, recovery_branch)
        self.assertLess(wait_for_child, action_branch)
        self.assertLess(action_branch, action_without_exit)

        for expected_rc in (0, 1, 8, 75, 76, 130):
            observed = subprocess.run(
                ["/usr/bin/setsid", "--wait", "/usr/bin/bash", "-c", f"exit {expected_rc}"],
                check=False,
                timeout=10,
            ).returncode
            self.assertEqual(observed, expected_rc)

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
        coalesce = function_body(
            session,
            "coalesce_terminal_action_reconcilers",
            "schedule_terminal_action_reconcile",
        )
        reconcile = function_body(
            session,
            "schedule_terminal_action_reconcile",
            "cancel_terminal_action_reconcile",
        )
        self.assertIn("/usr/bin/systemd-run", reconcile)
        self.assertIn("coalesce_terminal_action_reconcilers", reconcile)
        self.assertGreater(
            reconcile.index("coalesce_terminal_action_reconcilers"),
            reconcile.index("/usr/bin/systemd-run"),
        )
        self.assertIn("list-units", coalesce)
        self.assertIn("totem-terminal-action-reconcile-*.timer", coalesce)
        self.assertIn('/usr/bin/systemctl stop "$unit"', coalesce)
        self.assertIn('stop "${unit%.timer}.service"', coalesce)
        self.assertIn('[ "$unit" = "${keep_unit}.timer" ] && continue', coalesce)
        self.assertIn("--property=DefaultDependencies=no", reconcile)
        self.assertIn("--on-active=125s", reconcile)
        self.assertIn("--on-unit-active=30s", reconcile)
        self.assertIn("--timer-property=DefaultDependencies=no", reconcile)
        self.assertIn("--expire-terminal-action", reconcile)
        self.assertIn("--terminal-action-reconcile-unit", reconcile)
        self.assertIn("--terminal-action-player-was-active", reconcile)
        self.assertIn("--terminal-action-player-was-enabled", reconcile)
        self.assertIn("/opt/totem/bin/totem_open_settings_cleanup.sh", reconcile)
        action_start = session.index("    restart|poweroff)")
        action_block = session[action_start : session.index("    product_reset)", action_start)]
        prepared_index = action_block.index('write_terminal_action_marker "prepared"')
        reconcile_index = action_block.index('schedule_terminal_action_reconcile "$requested_action_id"')
        armed_index = action_block.index('write_terminal_action_marker "armed"')
        systemctl_index = action_block.index('/usr/bin/systemctl --no-block')
        accepted_index = action_block.index('write_terminal_action_marker "accepted"')
        pending_index = action_block.index('TERMINAL_ACTION_PENDING="true"')
        self.assertEqual(
            [prepared_index, reconcile_index, armed_index, pending_index, systemctl_index, accepted_index],
            sorted([prepared_index, reconcile_index, armed_index, pending_index, systemctl_index, accepted_index]),
        )
        acceptance_failure = action_block[
            action_block.index('if ! write_terminal_action_marker "accepted"') :
            action_block.index('c17_4_trace "totem_terminal_action_accepted"')
        ]
        self.assertNotIn("cancel_terminal_action_reconcile", acceptance_failure)
        self.assertNotIn('rm -f -- "$TERMINAL_ACTION_MARKER"', acceptance_failure)
        self.assertIn("totem_terminal_action_reconcile_schedule_failed", action_block)
        self.assertGreaterEqual(action_block.count("cancel_terminal_action_reconcile"), 1)
        failed_request = action_block[action_block.index('echo "totem_terminal_action_disarm_failed"') - 120 :]
        remove_index = failed_request.index('rm -f -- "$TERMINAL_ACTION_MARKER"')
        disarm_index = failed_request.index('TERMINAL_ACTION_PENDING="false"')
        cancel_index = failed_request.index("cancel_terminal_action_reconcile")
        self.assertEqual(
            [remove_index, disarm_index, cancel_index],
            sorted([remove_index, disarm_index, cancel_index]),
        )

        cleanup = CLEANUP_SCRIPT.read_text(encoding="utf-8")
        complete_start = cleanup.index("terminal_action_reconcile_complete() {")
        stop_start = cleanup.index("stop_terminal_action_reconcile() {", complete_start)
        complete_check = cleanup[complete_start:stop_start]
        self.assertIn('EXPIRE_TERMINAL_ACTION" = "true', complete_check)
        self.assertIn('[ "$PLAYER_RESTORE_START_RC" = "0" ]', complete_check)
        self.assertIn("player_service_stable", complete_check)
        self.assertNotIn("not_attempted", complete_check)
        stable_check = function_body(cleanup, "player_service_stable", "terminal_action_reconcile_complete")
        self.assertIn("systemctl is-active --quiet kiosky-player.service", stable_check)
        self.assertIn("ActiveEnterTimestampMonotonic", stable_check)
        self.assertIn("active_age_seconds >= minimum_seconds", stable_check)
        self.assertIn('TERMINAL_ACTION_PLAYER_STABLE_SEC="300"', cleanup)
        restore = function_body(cleanup, "restore_product_state", "enqueue_product_reset_gc")
        self.assertLess(
            restore.index("systemctl is-active --quiet kiosky-player.service"),
            restore.index("systemctl is-enabled kiosky-player.service"),
        )
        self.assertIn('PLAYER_RESTORE_START_MODE="already-active"', restore)
        self.assertIn('PLAYER_RESTORE_START_MODE="service-not-enabled"', restore)
        self.assertIn('PLAYER_RESTORE_START_MODE="previously-inactive"', restore)
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
                run_shell(f'write_terminal_action_marker armed restart "{other_request_id}"'),
                0,
                "arming must match the exact prepared request",
            )
            self.assertEqual(
                run_shell(f'write_terminal_action_marker armed restart "{request_id}"'),
                0,
            )
            self.assertEqual(
                run_shell("terminal_action_pending"),
                0,
                "a fresh armed action must preserve locks during shutdown",
            )
            self.assertNotEqual(
                run_shell(f'write_terminal_action_marker accepted restart "{other_request_id}"'),
                0,
                "acceptance must match the exact armed request",
            )
            self.assertEqual(
                run_shell(f'write_terminal_action_marker accepted restart "{request_id}"'),
                0,
            )
            self.assertEqual(
                run_shell("terminal_action_pending"),
                0,
                "a fresh accepted action must preserve locks during shutdown",
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

            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            fake_systemctl = fake_bin / "systemctl"
            fake_systemctl.write_text(
                """#!/bin/sh
printf '%s\\n' \"$*\" >> \"$FAKE_SYSTEMCTL_LOG\"
case \"${1:-}\" in
  is-active) [ \"${FAKE_PLAYER_ACTIVE:-false}\" = true ] ;;
  is-enabled) [ \"${FAKE_PLAYER_ENABLED:-false}\" = true ] ;;
  show)
    [ \"${FAKE_SHOW_VALID:-true}\" = true ] || { printf 'invalid\\n'; exit 0; }
    printf 'ActiveState=active\\n'
    printf 'SubState=running\\n'
    printf 'Result=success\\n'
    printf 'ExecMainStatus=0\\n'
    printf 'ActiveEnterTimestampMonotonic=%s\\n' \"${FAKE_ACTIVE_ENTER_US:-1}\"
    ;;
  enable) exit \"${FAKE_ENABLE_RC:-0}\" ;;
  start) exit \"${FAKE_START_RC:-0}\" ;;
  *) exit 1 ;;
esac
""",
                encoding="utf-8",
            )
            fake_systemctl.chmod(0o755)

            coalesce_systemctl = fake_bin / "coalesce-systemctl"
            coalesce_systemctl.write_text(
                """#!/bin/sh
printf '%s\\n' \"$*\" >> \"$FAKE_COALESCE_LOG\"
case \"${1:-}\" in
  list-units) printf '%b' \"${FAKE_LIST_UNITS:-}\"; exit \"${FAKE_LIST_RC:-0}\" ;;
  stop) exit \"${FAKE_STOP_RC:-0}\" ;;
  *) exit 1 ;;
esac
""",
                encoding="utf-8",
            )
            coalesce_systemctl.chmod(0o755)

            coalesce_probe = coalesce.replace("/usr/bin/systemctl", str(coalesce_systemctl))

            def run_coalesce_probe(listed: str, *, stop_rc: int = 0) -> tuple[int, str]:
                log = root / "coalesce.log"
                log.unlink(missing_ok=True)
                probe_env = dict(os.environ)
                probe_env.update(
                    {
                        "FAKE_COALESCE_LOG": str(log),
                        "FAKE_LIST_UNITS": listed,
                        "FAKE_STOP_RC": str(stop_rc),
                    }
                )
                current = "totem-terminal-action-reconcile-11111111222243338444555555555555"
                completed = subprocess.run(
                    ["bash", "-c", coalesce_probe + f'\ncoalesce_terminal_action_reconcilers "{current}"'],
                    env=probe_env,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                return completed.returncode, log.read_text(encoding="utf-8") if log.exists() else ""

            old = "totem-terminal-action-reconcile-aaaaaaaa222243338444555555555555"
            current = "totem-terminal-action-reconcile-11111111222243338444555555555555"
            coalesced_rc, coalesced_log = run_coalesce_probe(
                f"{old}.timer loaded active waiting old.timer old.service\\n"
                f"{current}.timer loaded active waiting current.timer current.service\\n"
            )
            self.assertEqual(coalesced_rc, 0)
            self.assertIn(f"stop {old}.timer", coalesced_log)
            self.assertIn(f"--no-block stop {old}.service", coalesced_log)
            self.assertNotIn(f"stop {current}.timer", coalesced_log)

            malformed_rc, malformed_log = run_coalesce_probe("unrelated.timer loaded active waiting x y\\n")
            self.assertNotEqual(malformed_rc, 0)
            self.assertNotIn("stop unrelated.timer", malformed_log)

            stop_failed_rc, _ = run_coalesce_probe(
                f"{old}.timer loaded active waiting old.timer old.service\\n",
                stop_rc=1,
            )
            self.assertNotEqual(stop_failed_rc, 0)

            restore_probe = (
                restore
                + "\n"
                + function_body(cleanup, "monotonic_uptime_seconds", "player_service_stable")
                + "\n"
                + stable_check
                + "\n"
                + complete_check
                + r'''
show_transition() { :; }
monotonic_uptime_seconds() { printf '%s\n' "$FAKE_UPTIME_SEC"; }
PLAYER_RESTORE_ATTEMPTED=false
PLAYER_RESTORE_START_MODE=none
PLAYER_RESTORE_START_RC=not_attempted
EXPIRE_TERMINAL_ACTION="$TEST_EXPIRE_TERMINAL_ACTION"
TERMINAL_ACTION_RECONCILE_UNIT="$TEST_TERMINAL_ACTION_RECONCILE_UNIT"
TERMINAL_ACTION_PLAYER_WAS_ACTIVE="$TEST_PLAYER_WAS_ACTIVE"
TERMINAL_ACTION_PLAYER_WAS_ENABLED="$TEST_PLAYER_WAS_ENABLED"
TERMINAL_ACTION_PLAYER_STABLE_SEC=300
REQUEST_DIR="$TEST_ROOT"
LOCK_DIR="$TEST_ROOT/missing-lock"
TERMINAL_ACTION_MARKER="$TEST_ROOT/missing-marker"
restore_product_state || true
printf '%s|%s\n' "$PLAYER_RESTORE_START_MODE" "$PLAYER_RESTORE_START_RC"
terminal_action_reconcile_complete
'''
            )

            def run_restore_probe(
                *,
                active: bool,
                enabled: bool,
                was_active: bool,
                was_enabled: bool,
                terminal: bool = True,
                start_rc: int = 0,
                enable_rc: int = 0,
                active_age_sec: int = 301,
                show_valid: bool = True,
            ) -> tuple[subprocess.CompletedProcess[str], str]:
                log = root / "systemctl.log"
                log.unlink(missing_ok=True)
                probe_env = dict(os.environ)
                probe_env.update(
                    {
                        "PATH": f"{fake_bin}:{probe_env['PATH']}",
                        "FAKE_SYSTEMCTL_LOG": str(log),
                        "FAKE_PLAYER_ACTIVE": str(active).lower(),
                        "FAKE_PLAYER_ENABLED": str(enabled).lower(),
                        "FAKE_START_RC": str(start_rc),
                        "FAKE_ENABLE_RC": str(enable_rc),
                        "FAKE_UPTIME_SEC": "1000",
                        "FAKE_ACTIVE_ENTER_US": str((1000 - active_age_sec) * 1_000_000),
                        "FAKE_SHOW_VALID": str(show_valid).lower(),
                        "TEST_EXPIRE_TERMINAL_ACTION": str(terminal).lower(),
                        "TEST_TERMINAL_ACTION_RECONCILE_UNIT": (
                            "totem-terminal-action-reconcile-11111111222243338444555555555555"
                            if terminal
                            else ""
                        ),
                        "TEST_PLAYER_WAS_ACTIVE": str(was_active).lower() if terminal else "",
                        "TEST_PLAYER_WAS_ENABLED": str(was_enabled).lower() if terminal else "",
                        "TEST_ROOT": str(root),
                    }
                )
                completed = subprocess.run(
                    ["bash", "-c", restore_probe],
                    env=probe_env,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                return completed, log.read_text(encoding="utf-8") if log.exists() else ""

            active, _ = run_restore_probe(
                active=True, enabled=False, was_active=True, was_enabled=False
            )
            self.assertEqual(active.returncode, 0)
            self.assertIn("already-active|0", active.stdout)

            fresh, _ = run_restore_probe(
                active=True,
                enabled=False,
                was_active=True,
                was_enabled=False,
                active_age_sec=10,
            )
            self.assertNotEqual(
                fresh.returncode,
                0,
                "an active blip must keep the reconciler running until the player is stable",
            )

            malformed, _ = run_restore_probe(
                active=True,
                enabled=False,
                was_active=True,
                was_enabled=False,
                show_valid=False,
            )
            self.assertNotEqual(
                malformed.returncode,
                0,
                "invalid systemd stability data must fail closed",
            )

            queued, queued_log = run_restore_probe(
                active=False, enabled=False, was_active=True, was_enabled=False
            )
            self.assertNotEqual(queued.returncode, 0)
            self.assertIn("no-block|0", queued.stdout)
            self.assertIn("start --no-block kiosky-player.service", queued_log)
            self.assertNotIn("enable kiosky-player.service", queued_log)

            previously_inactive, _ = run_restore_probe(
                active=False, enabled=False, was_active=False, was_enabled=False
            )
            self.assertEqual(previously_inactive.returncode, 0)
            self.assertIn("previously-inactive|0", previously_inactive.stdout)

            failed_start, _ = run_restore_probe(
                active=False,
                enabled=False,
                was_active=True,
                was_enabled=False,
                start_rc=5,
            )
            self.assertNotEqual(failed_start.returncode, 0)
            self.assertIn("no-block|5", failed_start.stdout)

            failed_enable, _ = run_restore_probe(
                active=False,
                enabled=False,
                was_active=False,
                was_enabled=True,
                enable_rc=6,
            )
            self.assertNotEqual(failed_enable.returncode, 0)
            self.assertIn("enable|6", failed_enable.stdout)

            disabled, _ = run_restore_probe(
                active=False,
                enabled=False,
                was_active=False,
                was_enabled=False,
                terminal=False,
            )
            self.assertNotEqual(disabled.returncode, 0)
            self.assertIn("service-not-enabled|1", disabled.stdout)

    def test_persistent_reset_can_recreate_its_runtime_request(self) -> None:
        session = SESSION_SCRIPT.read_text(encoding="utf-8")
        recovery_decision = function_body(
            session,
            "product_reset_recovery_can_open",
            "totem_core_capabilities_valid",
        )

        def recovery_can_open(rc: int, trigger: str) -> bool:
            return (
                subprocess.run(
                    [
                        "bash",
                        "-c",
                        recovery_decision
                        + f"\nproduct_reset_recovery_can_open {rc} {shlex.quote(trigger)}",
                    ],
                    check=False,
                    timeout=15,
                ).returncode
                == 0
            )

        self.assertTrue(recovery_can_open(55, "keyboard_f10_hold"))
        self.assertTrue(recovery_can_open(56, "keyboard_f10_hold"))
        self.assertFalse(recovery_can_open(57, "keyboard_f10_hold"))
        self.assertFalse(recovery_can_open(56, "product_reset_resume"))
        recovery_main = session[
            session.index("if product_reset_pending;", session.index('c15_trace "before_show_transition_2"')) :
            session.index('if product_reset_guard_required', session.index('c15_trace "before_show_transition_2"'))
        ]
        self.assertIn("product_reset_recovery_can_open", recovery_main)
        self.assertIn('PRODUCT_RESET_AVAILABLE="0"', recovery_main)

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
            image_embed = (REPO_ROOT / "scripts/build/totem_core_image_embed.py").read_text(encoding="utf-8")
            self.assertIn('TOTEM_CORE_CAPABILITIES = ("product-reset-v1", "totem-actions-v1")', image_embed)
            self.assertIn('TOTEM_CORE_PREVIOUS_CAPABILITIES = ("product-reset-v1", "totem-actions-v1")', image_embed)
            self.assertIn('current_target = f"releases/{TOTEM_CORE_VERSION}"', image_embed)
            self.assertIn('previous_target = f"releases/{TOTEM_CORE_PREVIOUS_VERSION}"', image_embed)
            self.assertIn('capabilities=TOTEM_CORE_CAPABILITIES', image_embed)
            self.assertIn('capabilities=TOTEM_CORE_PREVIOUS_CAPABILITIES', image_embed)
            self.assertIn('health.get("capabilities") != list(capabilities)', image_embed)
            self.assertIn(
                'embedded_health.get("capabilities") == list(TOTEM_CORE_CAPABILITIES)',
                image_embed,
            )
            self.assertIn(
                'state_data.get("previous") == expected_previous_state',
                image_embed,
            )

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
