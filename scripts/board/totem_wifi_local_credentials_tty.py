#!/usr/bin/env python3
"""C9.6.1 local HDMI/TTY Wi-Fi credential and apply flow.

The operator types Wi-Fi credentials on the totem itself. Values are written
only to a restricted temporary secrets file under /tmp, then the C9.6 adapter is
invoked locally with rollback-after-test.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import pathlib
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import termios
import time
import tty
from typing import Any


sys.dont_write_bytecode = True

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import totem_wifi_nm_adapter as adapter


DEFAULT_OUT_DIR = "/tmp/dadooh-c9-6-1-local-console-apply"
DEFAULT_SECRETS_DIR = "/tmp/dadooh-c9-6-local-secrets"
SECRETS_FILENAME = "secrets.json"
LOCAL_STATUS_FILENAME = "local-console-status.json"
DEFAULT_PROFILE_NAME = adapter.DEFAULT_PROFILE_NAME


def clear_screen() -> None:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def print_header(title: str) -> None:
    clear_screen()
    print("DADOOH")
    print(title)
    print("=" * 40)
    print()


def prepare_private_dir(raw_path: str) -> pathlib.Path:
    path = adapter.require_tmp_dir(raw_path)
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise adapter.AdapterError("diretorio temporario indisponivel")
    os.chmod(path, adapter.PRIVATE_DIR_MODE)
    return path


def atomic_write_private_json(path: pathlib.Path, payload: dict[str, Any], parent: pathlib.Path) -> None:
    if path.parent != parent:
        raise adapter.AdapterError("artifact path invalid")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(parent), text=True)
    tmp_path = pathlib.Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.chmod(tmp_path, adapter.PRIVATE_FILE_MODE)
        os.replace(tmp_path, path)
        os.chmod(path, adapter.PRIVATE_FILE_MODE)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def write_local_status(out_dir: pathlib.Path, payload: dict[str, Any]) -> None:
    status = {
        "schema_version": "dadooh-c9.6.1-local-console-wifi.v1",
        "generated_at_utc": adapter.utc_timestamp(),
        "interface": "local_hdmi_keyboard",
        "credentials_collected": False,
        "ssid_present": False,
        "psk_present": False,
        "secrets_file_created": False,
        "secrets_file_cleanup": False,
        "ssh_path_risk_acknowledged": True,
        "local_console_confirmed": True,
        "apply_requires_local_recovery": True,
        "apply_attempted": False,
        "manual_rollback_requested": False,
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "player_changed": False,
        "mpv_changed": False,
        "network_identifiers_published": False,
        "credential_values_published": False,
    }
    existing_path = out_dir / LOCAL_STATUS_FILENAME
    if existing_path.exists() and not existing_path.is_symlink():
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
        if isinstance(existing, dict):
            status.update(existing)
    status.update(payload)
    atomic_write_private_json(out_dir / LOCAL_STATUS_FILENAME, status, out_dir)


def write_secrets_file(secrets_dir: pathlib.Path, ssid: str, psk: str) -> pathlib.Path:
    secrets_path = secrets_dir / SECRETS_FILENAME
    if secrets_path.exists() and secrets_path.is_symlink():
        raise adapter.AdapterError("arquivo temporario invalido")
    payload = {
        "ssid": ssid,
        "psk": psk,
    }
    atomic_write_private_json(secrets_path, payload, secrets_dir)
    if secrets_path.is_symlink():
        raise adapter.AdapterError("arquivo temporario invalido")
    if stat.S_IMODE(secrets_dir.stat().st_mode) != adapter.PRIVATE_DIR_MODE:
        raise adapter.AdapterError("permissao temporaria invalida")
    if stat.S_IMODE(secrets_path.stat().st_mode) != adapter.PRIVATE_FILE_MODE:
        raise adapter.AdapterError("permissao temporaria invalida")
    return secrets_path


def collect_credentials(out_dir: pathlib.Path, secrets_dir: pathlib.Path) -> pathlib.Path:
    print_header("Teste Wi-Fi de Bancada")
    print("Digite a rede e senha neste totem.")
    print("Nada sera salvo em relatorio.")
    print()
    ssid = input("Rede Wi-Fi: ").strip()
    psk = getpass.getpass("Senha Wi-Fi: ")
    print()
    if not ssid or not psk:
        raise adapter.AdapterError("dados incompletos")
    if len(psk) < 8:
        raise adapter.AdapterError("senha invalida")
    confirm = input("Confirmar teste com rollback automatico? Digite SIM: ").strip().upper()
    if confirm != "SIM":
        raise adapter.AdapterError("operacao cancelada")

    secrets_path = write_secrets_file(secrets_dir, ssid, psk)
    write_local_status(
        out_dir,
        {
            "credentials_collected": True,
            "ssid_present": True,
            "psk_present": True,
            "secrets_file_created": True,
        },
    )
    return secrets_path


def set_private_file(path: pathlib.Path) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("w", encoding="utf-8")
    os.chmod(path, adapter.PRIVATE_FILE_MODE)
    return handle


def run_adapter_preflight(args: argparse.Namespace, out_dir: pathlib.Path) -> int:
    print_header("Teste Wi-Fi de Bancada")
    print("Verificando preflight local.")
    print("Nenhuma rede sera alterada.")
    print()
    command = [
        sys.executable,
        args.adapter_path,
        "--preflight-apply",
        "--timeout-sec",
        str(args.timeout_sec),
        "--profile-name",
        args.profile_name,
        "--out-dir",
        str(out_dir),
        "--allow-ssh-risk-with-local-console-confirmed",
        "--local-console-confirmed",
    ]
    stdout_path = out_dir / "preflight-stdout.json"
    with set_private_file(stdout_path) as handle:
        completed = subprocess.run(command, stdout=handle, stderr=subprocess.DEVNULL, text=True, check=False)
    print("Preflight concluido.")
    print("Resultado sanitizado gravado em /tmp.")
    if args.auto_exit_sec > 0:
        time.sleep(args.auto_exit_sec)
    else:
        input("Pressione Enter para sair.")
    return completed.returncode


def run_manual_rollback(args: argparse.Namespace, out_dir: pathlib.Path) -> None:
    command = [
        sys.executable,
        args.adapter_path,
        "--rollback-last",
        "--timeout-sec",
        str(args.timeout_sec),
        "--profile-name",
        args.profile_name,
        "--out-dir",
        str(out_dir),
    ]
    stdout_path = out_dir / "manual-rollback-stdout.json"
    with set_private_file(stdout_path) as handle:
        subprocess.run(command, stdout=handle, stderr=subprocess.DEVNULL, text=True, check=False)


class RawInput:
    def __enter__(self) -> "RawInput":
        self.fd = sys.stdin.fileno()
        self.old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

    def read_key(self, timeout_sec: float) -> str:
        ready, _, _ = select.select([sys.stdin], [], [], timeout_sec)
        if not ready:
            return ""
        return sys.stdin.read(1)


def monitor_apply_process(process: subprocess.Popen[Any], args: argparse.Namespace, out_dir: pathlib.Path) -> None:
    manual_rollback = False
    started = time.monotonic()
    with RawInput() as raw:
        while True:
            elapsed = int(time.monotonic() - started)
            print_header("Aplicando Wi-Fi com rollback automatico")
            print("Se a conexao cair, aguarde o rollback.")
            print("Pressione R para tentar rollback manual.")
            print("Pressione S para mostrar estado sanitizado.")
            print("Pressione Q para sair depois do fim.")
            print()
            print(f"Estado: {'em andamento' if process.poll() is None else 'finalizado'}")
            print(f"Tempo: {elapsed}s")
            key = raw.read_key(1).lower()
            if key == "r":
                manual_rollback = True
                run_manual_rollback(args, out_dir)
                write_local_status(out_dir, {"manual_rollback_requested": True})
            elif key == "s":
                print()
                print("Estado sanitizado gravado em /tmp.")
                time.sleep(1)
            elif key == "q" and process.poll() is not None:
                break
            if process.poll() is not None and args.auto_exit_sec > 0 and elapsed >= args.auto_exit_sec:
                break

    if manual_rollback:
        write_local_status(out_dir, {"manual_rollback_requested": True})


def run_apply(args: argparse.Namespace, out_dir: pathlib.Path, secrets_path: pathlib.Path) -> int:
    print_header("Aplicando Wi-Fi com rollback automatico")
    print("Se a conexao cair, aguarde o rollback.")
    print("O teste usa somente o perfil dedicado.")
    print()
    time.sleep(2)
    command = [
        sys.executable,
        args.adapter_path,
        "--apply",
        "--enable-real-apply",
        "--confirm-real-wifi-apply",
        adapter.CONFIRM_REAL_WIFI_APPLY_LOCAL_CONSOLE,
        "--secrets-file",
        str(secrets_path),
        "--profile-name",
        args.profile_name,
        "--timeout-sec",
        str(args.timeout_sec),
        "--rollback-after-test",
        "--cleanup-secrets-file",
        "--allow-ssh-risk-with-local-console-confirmed",
        "--local-console-confirmed",
        "--out-dir",
        str(out_dir),
    ]
    stdout_path = out_dir / "apply-stdout.json"
    stdout_handle = set_private_file(stdout_path)
    try:
        process = subprocess.Popen(command, stdout=stdout_handle, stderr=subprocess.DEVNULL, text=True)
        write_local_status(out_dir, {"apply_attempted": True})
        monitor_apply_process(process, args, out_dir)
        return_code = process.wait()
        write_local_status(out_dir, {"secrets_file_cleanup": not secrets_path.exists()})
        return return_code
    finally:
        stdout_handle.close()


def assert_no_forbidden_values(text: str) -> None:
    lowered = text.lower()
    for value in adapter.SENSITIVE_MARKERS:
        if value.lower() in lowered:
            raise AssertionError(f"leaked {value}")


def run_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c9-6-1-local-console-self-test-", dir="/tmp"))
    try:
        out_dir = prepare_private_dir(str(root / "out"))
        secrets_dir = prepare_private_dir(str(root / "secrets"))
        secrets = write_secrets_file(secrets_dir, "FAKE-STORE-WIFI", "fake-password")
        write_local_status(
            out_dir,
            {
                "credentials_collected": True,
                "ssid_present": True,
                "psk_present": True,
                "secrets_file_created": True,
            },
        )
        assert stat.S_IMODE(secrets_dir.stat().st_mode) == adapter.PRIVATE_DIR_MODE
        assert stat.S_IMODE(secrets.stat().st_mode) == adapter.PRIVATE_FILE_MODE
        assert stat.S_IMODE((out_dir / LOCAL_STATUS_FILENAME).stat().st_mode) == adapter.PRIVATE_FILE_MODE
        status_text = (out_dir / LOCAL_STATUS_FILENAME).read_text(encoding="utf-8")
        assert_no_forbidden_values(status_text)
        assert not secrets.is_symlink()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Wi-Fi credentials locally on HDMI/TTY and run C9.6.1 apply with rollback.",
        allow_abbrev=False,
    )
    parser.add_argument("--adapter-path", default=str(SCRIPT_DIR / "totem_wifi_nm_adapter.py"))
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--secrets-dir", default=DEFAULT_SECRETS_DIR)
    parser.add_argument("--profile-name", default=DEFAULT_PROFILE_NAME)
    parser.add_argument("--timeout-sec", type=int, default=45)
    parser.add_argument("--auto-exit-sec", type=int, default=10)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-test", action="store_true")
    modes.add_argument("--preflight-only", action="store_true")
    modes.add_argument("--apply-rollback-after-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.timeout_sec <= 0 or args.timeout_sec > 120:
            raise adapter.AdapterError("timeout invalido")
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0
        out_dir = prepare_private_dir(args.out_dir)
        secrets_dir = prepare_private_dir(args.secrets_dir)
        adapter.require_allowed_profile_name(args.profile_name)
        if args.preflight_only:
            return run_adapter_preflight(args, out_dir)
        secrets_path = collect_credentials(out_dir, secrets_dir)
        return run_apply(args, out_dir, secrets_path)
    except adapter.AdapterError as exc:
        try:
            out_dir = prepare_private_dir(getattr(args, "out_dir", DEFAULT_OUT_DIR))
            write_local_status(out_dir, {"error_public": "operacao indisponivel"})
        except Exception:
            pass
        print_header("Teste Wi-Fi de Bancada")
        print("Nao foi possivel continuar.")
        print(str(exc))
        time.sleep(4)
        return 2
    except KeyboardInterrupt:
        print_header("Teste Wi-Fi de Bancada")
        print("Operacao cancelada.")
        time.sleep(2)
        return 130
    except Exception:
        print_header("Teste Wi-Fi de Bancada")
        print("Nao foi possivel continuar.")
        time.sleep(4)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
