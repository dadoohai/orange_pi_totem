#!/usr/bin/env python3
"""Derive the C18.IMAGE-LAB.1 HW-decode image-lab from the validated C17.4.2 image.

Offline, userspace-only, rootless (debugfs — no mount, no root, no Armbian/kernel
rebuild, no apt, no board, no card). It copies the hardware-validated C17.4.2 image and:
  * injects the proven Cedrus/V4L2-Request HW-decode userspace stack
    (FFmpeg fork libav* + mpv + libplacebo + libass/freetype/fribidi) under
    /opt/totem/hwdecode/{bin,lib};
  * installs a wrapper /opt/totem/bin/totem-mpv-hwdecode that runs the custom mpv with
    the HW-decode fallback display path forced (--vo=gpu --gpu-context=drm
    --hwdec=v4l2request-copy, override-last) and LD_LIBRARY_PATH scoped to the stack;
  * points the embedded player (DEFAULT_CONFIG mpv_path in /opt/totem/kiosky-player/
    kiosk.py) at that wrapper — preserving IPC/playlist/duration/sync/rotation logic;
  * injects the current governed updater (foundation totem_updatectl.py), which
    includes the settings/update transaction guard that C17.4.2 predates;
  * embeds the C17.6 totem-core update layout so wizard/core fixes are OTA-ready
    from first boot (/data/core/totem current release, /opt fallback scripts and
    wrappers);
  * writes the image marker. The default remains image-lab
    (artifact_private/final_image=false/not_for_production); production identity
    requires --image-profile production.

It does NOT touch kernel/U-Boot/DTB/BSP, real config, or media/cache. Production
derivation disables the old overlayroot path and reads one external support
credential only to replace the root hash; the plaintext is never copied into the image.
"""
from __future__ import annotations
import argparse, atexit, hashlib, hmac, json, math, os, re, shutil, stat, subprocess, sys, tarfile, tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derive_c15_2_1_homolog_image as base
import totem_core_image_embed

ARM = Path("/home/builder/totem-os/armbian-build-v25.11/output/images")
REPO_ROOT = Path(__file__).resolve().parents[2]
CURRENT_GOLDEN_PATH = REPO_ROOT / "docs" / "evidence" / "c18-update-validation" / "current-golden.json"
CURRENT_GOLDEN = json.loads(CURRENT_GOLDEN_PATH.read_text(encoding="utf-8"))
BASE_IMAGE = ARM / ("Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
                    "6.12.58-c12-ro-lab-c17-4-2-settings-restore-clean_minimal.img")
TAG = str(CURRENT_GOLDEN["image_tag"])   # default golden; override only for explicit candidate builds.
VERSION = str(CURRENT_GOLDEN["image_version"])
OUT_IMAGE = ARM / (f"Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
                   f"6.12.58-{TAG}_minimal.img")
OUT_SHA = Path(str(OUT_IMAGE) + ".sha256")
OUT_READY = Path(str(OUT_IMAGE) + ".ready.json")

BUNDLE = Path("/tmp/ffbuild/bundle")
FFMPEG_CLI = Path("/tmp/ffbuild/ffmpeg.stripped")
R4_UPDATECTL = REPO_ROOT / "scripts" / "board" / "totem_updatectl.py"
PLAYER_RUNTIME_KIOSK = REPO_ROOT / "player-runtime" / "kiosky-player" / "kiosk.py"
PLAYER_RUNTIME_SOURCE = REPO_ROOT / "player-runtime" / "kiosky-player" / "SOURCE.json"
PLAYER_RUNTIME_PRODUCTION_AUTH = REPO_ROOT / "scripts" / "board" / "player_runtime_production_autopull.json"
PLAYER_RUNTIME_PRODUCTION_AUTH_GATE = (
    REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_production_autopull_authorization_gate.py"
)
PRODUCTION_IDENTITY_SCRIPT_SOURCE = REPO_ROOT / "scripts" / "board" / "totem_production_identity_init.sh"
PRODUCTION_IDENTITY_UNIT_SOURCE = (
    REPO_ROOT / "scripts" / "board" / "systemd" / "totem-production-identity-init.service"
)
PRODUCTION_SSH_DROPIN_SOURCE = (
    REPO_ROOT / "scripts" / "board" / "systemd" / "ssh-production-identity.conf"
)
PRODUCTION_CREDENTIAL_GENERATOR_SOURCE = (
    REPO_ROOT / "scripts" / "build" / "generate_c18_production_support_credential.py"
)
PRODUCTION_SETTINGS_POLICY_SOURCE = (
    REPO_ROOT / "scripts" / "board" / "totem_settings_production_apply_policy.py"
)
PRODUCTION_OPEN_SETTINGS_UNIT_SOURCE = (
    REPO_ROOT / "scripts" / "board" / "totem-open-settings.production.service"
)

HWDIR = "/opt/totem/hwdecode"
WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
KIOSK = "/opt/totem/kiosky-player/kiosk.py"
UPDATECTL = "/opt/totem/bin/totem-updatectl"
MARKER = str(CURRENT_GOLDEN["image_marker_path"])
PRODUCTION_TAG = "c18-hwdecode-prod-19-c26"
PRODUCTION_VERSION = "c18.image-prod.19-c26"
PRODUCTION_MARKER = f"/etc/dadooh/{PRODUCTION_TAG}-image"
PRODUCTION_PREDECESSOR_TAG = "c18-hwdecode-prod-16-c26-candidate"
PRODUCTION_PREDECESSOR_SHA256 = "18c1b42c57809b704820f5dfa383fb05a3d254d50745cb217440f241c75e1168"
PRODUCTION_IMAGE_BOUND_TRANSACTION_COMMIT = "bfb0d04489ac4251908ba27396bd8ed37bead3f8"
PRODUCTION_IMAGE_BOUND_PLAYBACK_SUMMARY_COMMIT = "c075a5572148ed25aed000a22202f918c4157fda"
PRODUCTION_SUCCESSOR_SCOPE = (
    "image_identity_prod19_c26",
    "totem_core_c26_9_current_c26_8_previous_embedded",
    "totem_core_two_distinct_product_reset_slots",
    "playback_health_summary_c075a55",
    "player_runtime_c25b_exact_target_preserved",
)
PANFROST_SH = "/opt/totem/bin/totem-panfrost-rebind.sh"
PANFROST_UNIT = "/etc/systemd/system/totem-panfrost-rebind.service"
PANFROST_WANTS = "/etc/systemd/system/multi-user.target.wants/totem-panfrost-rebind.service"
C18_STABILITY_DROPIN = "/etc/systemd/system/kiosky-player.service.d/30-c18-stability.conf"
HOMOLOGATION_SEED = "/data/state/totem-settings/private-values.seed.json"
PRODUCTION_IDENTITY_SCRIPT = "/opt/totem/bin/totem-production-identity-init.sh"
PRODUCTION_IDENTITY_UNIT = "/etc/systemd/system/totem-production-identity-init.service"
PRODUCTION_IDENTITY_WANTS = (
    "/etc/systemd/system/multi-user.target.wants/totem-production-identity-init.service"
)
PRODUCTION_SSH_DROPIN = "/etc/systemd/system/ssh.service.d/10-dadooh-production-identity.conf"
PRODUCTION_OPEN_SETTINGS_UNIT = "/etc/systemd/system/totem-open-settings.service"
PRODUCTION_SETTINGS_POLICY = "/opt/totem/bin/totem_settings_production_apply_policy.py"
PRODUCTION_LAB_SETTINGS_POLICY = "/opt/totem/bin/totem_settings_lab_apply_policy.sh"
PRODUCTION_ARMBIAN_ENV = "/boot/armbianEnv.txt"
PRODUCTION_ARMBIAN_FIRSTRUN_CONFIG = "/etc/default/armbian-firstrun"
PRODUCTION_ARMBIAN_FIRSTRUN_SCRIPT = "/usr/lib/armbian/armbian-firstrun"
PRODUCTION_ARMBIAN_FIRSTRUN_UNIT = "/lib/systemd/system/armbian-firstrun.service"
PRODUCTION_ARMBIAN_FIRSTRUN_WANTS = (
    "/etc/systemd/system/multi-user.target.wants/armbian-firstrun.service"
)
PRODUCTION_ROOTFS_RESIZE_SCRIPT = "/usr/lib/armbian/armbian-resize-filesystem"
PRODUCTION_ROOTFS_RESIZE_UNIT = "/lib/systemd/system/armbian-resize-filesystem.service"
PRODUCTION_ROOTFS_RESIZE_WANTS = (
    "/etc/systemd/system/basic.target.wants/armbian-resize-filesystem.service"
)
PRODUCTION_ROOTFS_RESIZE_DISABLE_MARKER = "/root/.no_rootfs_resize"
KIOSKY_PLAYER_COMMIT_MARKER = "/opt/totem/kiosky-player/.kiosky_player_commit"
PRODUCTION_SHADOW_PATHS = ("/etc/shadow", "/etc/shadow-")
PRODUCTION_SUPPORT_PASSWORD_MIN_LENGTH = 48
PRODUCTION_SUPPORT_PASSWORD_MAX_LENGTH = 128
PRODUCTION_SUPPORT_PASSWORD_MIN_UNIQUE_CHARS = 20
PRODUCTION_SUPPORT_PASSWORD_MIN_SYMBOL_DISTRIBUTION = 4.25
PRODUCTION_CREDENTIAL_PROVENANCE_SCHEMA = "dadooh.c18.production_support_credential_provenance.v1"
PRODUCTION_OPENSSL = Path("/usr/bin/openssl")
PRODUCTION_OPENSSL_SHA256 = "724acbe911513d13f52bae0b8969b20336cd8618fc67898a6bf7847bf1a270ad"
PRODUCTION_OPENSSL_VERSION_PREFIX = "OpenSSL 3.0.13 "
PRODUCTION_DEBUGFS = Path("/usr/sbin/debugfs")
PRODUCTION_DEBUGFS_SHA256 = "1e83118cc9582afcad2711fbb7f40f56668adccb386d988cb6d9ad5c2d001049"
PRODUCTION_E2FSCK = Path("/usr/sbin/e2fsck")
PRODUCTION_E2FSCK_SHA256 = "c69c6315f602d389821b3a1dab1308618616259400f2cf5d997243c4a83c284c"
PRODUCTION_E2FSPROGS_VERSION_PREFIX = "1.47.0"
PRODUCTION_ZEROFREE = Path("/home/builder/.local/libexec/dadooh/zerofree")
PRODUCTION_ZEROFREE_SHA256 = "42f959837e7c5fab212e7e0034392f59edbecd729c9413b5e241751af82f562a"
PRODUCTION_OUTPUT_MIN_FREE_BYTES = 12 * 1024 * 1024 * 1024
PRODUCTION_WSL_HOST_MIN_FREE_BYTES = 8 * 1024 * 1024 * 1024
PRODUCTION_OVERLAYROOT_PATHS = (
    "/etc/overlayroot.conf",
    "/etc/overlayroot.conf.c12-image-lab-base",
    "/etc/dadooh/c12-overlayfs-kernel-policy",
    "/etc/initramfs-tools/hooks/dadooh-c12-overlayroot-marker",
)
PRODUCTION_FORBIDDEN_LAB_PATHS = (
    "/root/.not_logged_in_yet",
    "/etc/dadooh/image-lab-firstboot-autoconfig.present",
    "/etc/dadooh/c12-lab-firstboot-mode",
    "/etc/dadooh/c13-homologation-build-apt-policy",
    "/etc/dadooh/c13-homologation-private-seed",
    "/etc/dadooh/c15-2-4-clean-board-fixes",
    "/etc/dadooh/c17-4-firstboot-visual-f10-image",
    "/etc/dadooh/c17-4-2-settings-restore-clean-image",
    "/etc/systemd/system/multi-user.target.wants/totem-lab-firstboot-autoconfig.service",
    "/etc/systemd/system/totem-lab-firstboot-autoconfig.service",
    "/opt/totem/bin/totem_lab_firstboot_autoconfig.sh",
    PRODUCTION_LAB_SETTINGS_POLICY,
    "/data/state/totem-settings/homologation-seed.enabled",
    "/data/state/totem-read-only-image-lab/integration.json",
)
PRODUCTION_EMBEDDED_SSH_HOST_KEYS = (
    "/etc/ssh/ssh_host_rsa_key",
    "/etc/ssh/ssh_host_rsa_key.pub",
    "/etc/ssh/ssh_host_ecdsa_key",
    "/etc/ssh/ssh_host_ecdsa_key.pub",
    "/etc/ssh/ssh_host_ed25519_key",
    "/etc/ssh/ssh_host_ed25519_key.pub",
)
PRODUCTION_SEED_IDENTITY_FIELDS = {
    "api_key",
    "environment_id",
    "station_id",
    "telemetry_token",
}

MPV_PATH_OLD = '"mpv_path": "mpv",'
MPV_PATH_NEW = f'"mpv_path": "{WRAPPER}",'
PLAYER_RUNTIME_KIOSK_SHA256 = "7b67003a450902ddd4ea5d8c9f11653a43b9e55df0c45ccd4496be08188df3f0"
PLAYER_RUNTIME_BASELINE_VERSION = "c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4"
PLAYER_RUNTIME_BASELINE_SOURCE_COMMIT = "54308e4a09ef693dbfb3d6b31ce9626908ca0c16"
PLAYER_RUNTIME_BASELINE_PAYLOAD_SHA256 = "b6e1a58b6434107a5af43d27bc07f19b0255bcc58c86deac59be6acc2742b70d"
PLAYER_RUNTIME_BASELINE_MANIFEST_SHA256 = "d3199e34a42e992ec40567b0a7c9620c73bfab4979454c7024d1bea74e83e55d"
PLAYER_RUNTIME_BASELINE_RELEASE_GATE_SHA256 = "f03fa5e295530459dbb0d0b324186567a3a82b8f5f6aeb9fcba8b7dad38a250f"
C25_SYSTEM_FFMPEG = "/usr/bin/ffmpeg"
C25_SYSTEM_FFPROBE = "/usr/bin/ffprobe"
C25_SURFACE_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
BASE_IMAGE_SHA256 = "184ecdff1da3fc5f2f819b9be1a67da9e3cfaa87b8bdede7badddf2c1a22c5af"
HWD_STACK_BUNDLE_SHA256 = "96e0ce3ff34edced247e2deca03e0d848bd3b26142d56267e95ef295bb071967"
FFMPEG_CLI_SHA256 = "cfbfa5a9938b0933437241bab89373b93bb1bfd5f87f9881c068b522a0fc6e16"
PLAYER_RUNTIME_REQUIRED_PATCHES = {
    "DEFAULT_CONFIG.mpv_path": ("mpv", WRAPPER),
    "MPVController._stop_locked": (
        "close IPC then signal MPV process group",
        "request MPV IPC quit, including fresh IPC fallback, before signal fallback",
    ),
    "MPVController.load_file/preload_next": (
        "IPC write success implies media switch",
        "fresh IPC path verification before trusting loadfile or preloaded playlist-next",
    ),
    "MPVController fresh IPC transport": (
        "fresh queries plus an unread persistent command socket",
        "startup probe closes immediately and every control command uses a serialized fresh request/response",
    ),
    "download_media/media_items_from_saved/media_items_from_cache": (
        "image extensions are admitted directly into MPV",
        "still images are prepared as local H.264 MP4 sidecars before playlist admission",
    ),
    "MPVController.wait_for_local_frame_evidence/playback status": (
        "path acceptance alone can publish first_frame_ready",
        "one stable MPV generation, matching path, configured VO and video parameters are required; video requires frame progress and still-image sidecars require frame availability",
    ),
    "startup feedback/public surface": (
        "one legacy landscape placeholder with path-only acceptance",
        "C25 public loading, unavailable and recovery surfaces with landscape/portrait layout and local VO/frame evidence",
    ),
    "startup feedback/MPV transport": (
        "direct SVG load, unsupported by the production MPV decoder set",
        "versioned one-frame H.264 generated atomically by the image-bound ffmpeg and verified before load",
    ),
}
PLAYER_RUNTIME_TEARDOWN_TOKENS = (
    "def _request_quit",
    "def _fresh_ipc_command",
    '{"command": ["quit"]}',
    "MPV IPC fresh command sent",
    "MPV IPC quit timeout; falling back to SIGTERM",
    "os.killpg(self._proc.pid, signal.SIGTERM)",
    "os.killpg(self._proc.pid, signal.SIGKILL)",
)

# Workaround for the H618 panfrost boot deferred-probe race (-110): bind the GPU before the
# player if the render node is missing. Userspace only — no kernel/DTB/cmdline change.
PANFROST_SH_BODY = (
    "#!/bin/sh\n"
    "# C18: ensure the panfrost GPU is bound before the player (boot deferred-probe race\n"
    "# workaround). If /dev/dri/renderD128 is absent, (re)bind 1800000.gpu. No-op if present.\n"
    "i=0\n"
    "while [ \"$i\" -lt 8 ]; do\n"
    "  [ -e /dev/dri/renderD128 ] && exit 0\n"
    "  echo 1800000.gpu > /sys/bus/platform/drivers/panfrost/bind 2>/dev/null || true\n"
    "  [ -e /dev/dri/renderD128 ] && exit 0\n"
    "  i=$((i+1)); sleep 1\n"
    "done\n"
    "[ -e /dev/dri/renderD128 ]\n"
)
PANFROST_UNIT_BODY = (
    "[Unit]\n"
    "Description=Dadooh totem: bind panfrost GPU (boot deferred-probe race workaround)\n"
    "DefaultDependencies=no\n"
    "After=systemd-modules-load.service\n"
    "Before=kiosky-player.service\n"
    "ConditionPathExists=!/dev/dri/renderD128\n"
    "\n"
    "[Service]\n"
    "Type=oneshot\n"
    "RemainAfterExit=yes\n"
    f"ExecStart={PANFROST_SH}\n"
    "\n"
    "[Install]\n"
    "WantedBy=multi-user.target\n"
)

WRAPPER_SH = (
    "#!/bin/sh\n"
    "# C18 HW-decode wrapper. Forces the\n"
    "# copy-back fallback path (override-last) + scoped LD_LIBRARY_PATH; preserves\n"
    "# IPC/rotation/etc. C18.IMAGE-LAB.1d uses v4l2request-copy because the zero-copy\n"
    "# drm_prime->panfrost path generated runtime panfrost js faults on some portrait\n"
    "# media in hardware validation.\n"
    "# Strips options the minimal (no-Lua) custom mpv lacks: stock mpv's --no-osc comes from\n"
    "# the OSC Lua script; with -Dlua=disabled that option does not exist, so the player's\n"
    "# --no-osc made mpv fatal-exit before creating the IPC socket (the C18.IMAGE-LAB.1b\n"
    "# 'iniciando player' crash-loop). Dropping it is correct (no OSC to disable).\n"
    "export LD_LIBRARY_PATH=/opt/totem/hwdecode/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\n"
    'for a in "$@"; do\n'
    "  shift\n"
    '  case "$a" in --no-osc) continue ;; esac\n'
    '  set -- "$@" "$a"\n'
    "done\n"
    'exec /opt/totem/hwdecode/bin/mpv "$@" --vo=gpu --gpu-context=drm --hwdec=v4l2request-copy\n'
)

C18_STABILITY_DROPIN_BODY = (
    "[Service]\n"
    "# C18.IMAGE-LAB.1d: C17.4 firstboot trace is diagnostic-only. Keep it out of\n"
    "# /data so slow/failing mmc I/O cannot block kiosky-player startup before\n"
    "# kiosk.py launches.\n"
    "Environment=TOTEM_C17_4_FIRSTBOOT_TRACE_DIR=/run/totem/c17-4-firstboot\n"
)

SOURCES = {
    "ffmpeg_source": "github.com/Kwiboo/FFmpeg", "ffmpeg_commit": "2af4006",
    "ffmpeg_branch": "v4l2request-2024-v2",
    "mpv_source": "github.com/Kwiboo/mpv", "mpv_commit": "8670d2e",
    "mpv_branch": "v4l2request-test-20240808",
    "libplacebo_commit": "64c1954", "libplacebo_config": "opengl=enabled; vulkan/d3d11/shaderc/glslang/lcms disabled",
}


def sh(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def validate_production_ext4_tools() -> dict:
    tools = (
        ("debugfs", PRODUCTION_DEBUGFS, PRODUCTION_DEBUGFS_SHA256),
        ("e2fsck", PRODUCTION_E2FSCK, PRODUCTION_E2FSCK_SHA256),
    )
    metadata = {}
    for name, expected_path, expected_sha256 in tools:
        resolved = shutil.which(name)
        if not resolved or Path(resolved).resolve() != expected_path.resolve():
            raise SystemExit(f"BLOCKED: pinned {name} path mismatch")
        if not expected_path.is_file() or not os.access(expected_path, os.X_OK):
            raise SystemExit(f"BLOCKED: pinned {name} is unavailable")
        if base.file_sha256(expected_path) != expected_sha256:
            raise SystemExit(f"BLOCKED: pinned {name} hash mismatch")
        version = sh([str(expected_path), "-V"])
        if version.returncode != 0 or PRODUCTION_E2FSPROGS_VERSION_PREFIX not in version.stdout:
            raise SystemExit(f"BLOCKED: pinned {name} version mismatch")
        metadata[name] = {
            "path": str(expected_path),
            "sha256": expected_sha256,
            "version": version.stdout.splitlines()[0].strip(),
        }
    return metadata


def require_free_space(path: Path, minimum_bytes: int, *, label: str) -> int:
    free_bytes = shutil.disk_usage(path).free
    if free_bytes < minimum_bytes:
        raise SystemExit(
            f"BLOCKED: insufficient {label} free space; "
            f"required={minimum_bytes} available={free_bytes}"
        )
    return free_bytes


def debugfs_batch_errors(output: str) -> list[str]:
    current_command = "<none>"
    errors = []
    suspicious = (
        "error",
        "failed",
        "file not found",
        "no such file",
        "couldn't",
        "already exists",
        "directory not empty",
        "not a directory",
        "unknown request",
        "invalid argument",
    )
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("debugfs: "):
            current_command = line.removeprefix("debugfs: ").strip()
            continue
        lower = line.lower()
        if not line or not any(token in lower for token in suspicious):
            continue
        command = current_command.split(maxsplit=1)[0] if current_command else ""
        expected_missing_delete = (
            command in {"rm", "rmdir"}
            and ("file not found" in lower or "no such file" in lower)
        )
        expected_existing_directory = command == "mkdir" and "directory already exists" in lower
        if expected_missing_delete or expected_existing_directory:
            continue
        errors.append(f"{current_command}: {line}")
    return errors


def run_debugfs_batch_strict(rootfs: Path, commands: list[str], work_dir: Path) -> str:
    command_file = work_dir / "debugfs.production.commands"
    command_file.write_text("\n".join(commands) + "\n", encoding="utf-8")
    result = subprocess.run(
        [str(PRODUCTION_DEBUGFS), "-w", "-f", str(command_file), str(rootfs)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = result.stdout or ""
    errors = debugfs_batch_errors(output)
    if result.returncode != 0 or errors:
        detail = "\n".join(errors[:30])
        raise SystemExit(
            f"BLOCKED: production debugfs batch failed rc={result.returncode}"
            + (f"\n{detail}" if detail else "")
        )
    return output


def atomic_write(path: Path, data: bytes, *, mode: int = 0o644) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def publish_file_exclusive(source: Path, target: Path) -> None:
    os.link(source, target)
    source.unlink()


def publish_bytes_exclusive(target: Path, data: bytes, *, mode: int = 0o644) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temp_path = Path(temp_name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.link(temp_path, target)
    finally:
        temp_path.unlink(missing_ok=True)


def sanitize_production_armbian_env(text: str) -> str:
    lines = []
    removed = 0
    for line in text.splitlines():
        if line.startswith("extraargs="):
            key, value = line.split("=", 1)
            tokens = value.split()
            kept = [token for token in tokens if not token.startswith("overlayroot=")]
            removed += len(tokens) - len(kept)
            line = f"{key}={' '.join(kept)}"
        lines.append(line)
    if removed != 1:
        raise SystemExit(
            f"BLOCKED: expected exactly one overlayroot boot argument in base image, found {removed}"
        )
    result = "\n".join(lines) + "\n"
    if "overlayroot=" in result:
        raise SystemExit("BLOCKED: overlayroot boot argument survived production sanitization")
    return result


def sanitize_production_armbian_firstrun(text: str) -> str:
    expected = "OPENSSHD_REGENERATE_HOST_KEYS=true"
    lines = text.splitlines()
    if lines.count(expected) != 1:
        raise SystemExit(
            "BLOCKED: expected exactly one enabled Armbian SSH host-key regeneration setting"
        )
    lines[lines.index(expected)] = "OPENSSHD_REGENERATE_HOST_KEYS=false"
    result = "\n".join(lines) + ("\n" if text.endswith(("\n", "\r")) else "")
    if (
        result.splitlines().count(expected) != 0
        or result.splitlines().count("OPENSSHD_REGENERATE_HOST_KEYS=false") != 1
    ):
        raise SystemExit("BLOCKED: failed to disable Armbian SSH host-key regeneration")
    return result


def debugfs_fast_symlink_target(rootfs: Path, path: str) -> str:
    output = base.debugfs(rootfs, f"stat {path}")
    match = re.search(r'^Fast link dest: "([^"]+)"$', output, flags=re.MULTILINE)
    return match.group(1) if match else ""


def systemd_active_directive_values(unit_text: str, directive: str) -> list[str]:
    pattern = re.compile(rf"^\s*{re.escape(directive)}\s*=\s*(.*)$")
    values = []
    for raw_line in unit_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        match = pattern.fullmatch(raw_line)
        if match:
            values.append(match.group(1).strip())
    return values


def systemd_unit_has_exact_directive(unit_text: str, directive: str, value: str) -> bool:
    return systemd_active_directive_values(unit_text, directive) == [value]


def systemd_unit_directive_has_token(unit_text: str, directive: str, token: str) -> bool:
    return any(
        token in value.split()
        for value in systemd_active_directive_values(unit_text, directive)
    )


def resolve_zerofree(explicit: str | None) -> Path:
    candidate = Path(explicit) if explicit else PRODUCTION_ZEROFREE
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise SystemExit(
            "BLOCKED: zerofree is required for production images; install it or pass --zerofree"
        )
    candidate = candidate.resolve()
    if base.file_sha256(candidate) != PRODUCTION_ZEROFREE_SHA256:
        raise SystemExit("BLOCKED: pinned zerofree hash mismatch")
    return candidate


def run_zerofree_scan(tool: Path, filesystem: Path) -> tuple[subprocess.CompletedProcess[str], str]:
    result = sh([str(tool), "-n", "-v", str(filesystem)])
    normalized = result.stdout.replace("\r", "\n")
    summaries = [line.strip() for line in normalized.splitlines() if "/" in line]
    summary = summaries[-1] if summaries else ""
    return result, summary


def debugfs_read_bytes(rootfs: Path, path: str, *, allow_empty: bool = False) -> bytes:
    result = subprocess.run(
        [str(PRODUCTION_DEBUGFS), "-R", f"cat {path}", str(rootfs)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 or (not result.stdout and not allow_empty):
        raise SystemExit(f"BLOCKED: failed to read required image file {path}")
    return result.stdout


def read_private_build_input(path: Path, *, max_bytes: int) -> bytes:
    candidate = Path(os.path.abspath(path.expanduser()))
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(candidate, flags)
    except OSError as exc:
        raise SystemExit("BLOCKED: private production build input is unavailable") from exc
    try:
        actual_path = Path(os.readlink(f"/proc/self/fd/{fd}")).resolve()
        if actual_path == REPO_ROOT or REPO_ROOT in actual_path.parents:
            raise SystemExit("BLOCKED: private production build input must stay outside the source repo")
        parent_stat = actual_path.parent.stat()
        if parent_stat.st_uid != os.getuid() or stat.S_IMODE(parent_stat.st_mode) & 0o077:
            raise SystemExit("BLOCKED: private production build input directory must be private to the build user")
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise SystemExit("BLOCKED: private production build input must be a regular file")
        if before.st_nlink != 1:
            raise SystemExit("BLOCKED: private production build input must not have hardlinks")
        if stat.S_IMODE(before.st_mode) != 0o600:
            raise SystemExit("BLOCKED: private production build input file mode must be 0600")
        if before.st_uid != os.getuid():
            raise SystemExit("BLOCKED: private production build input must be owned by the build user")
        with os.fdopen(fd, "rb", closefd=False) as private_file:
            raw = private_file.read(max_bytes + 1)
        after = os.fstat(fd)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode, before.st_uid)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode, after.st_uid)
        if identity_after != identity_before:
            raise SystemExit("BLOCKED: private production build input changed while being read")
    finally:
        os.close(fd)
    if len(raw) > max_bytes:
        raise SystemExit("BLOCKED: private production build input exceeds size policy")
    return raw


def load_production_support_password(path: Path) -> str:
    raw = read_private_build_input(path, max_bytes=PRODUCTION_SUPPORT_PASSWORD_MAX_LENGTH + 2)
    if raw.count(b"\n") != 1 or not raw.endswith(b"\n"):
        raise SystemExit("BLOCKED: production support credential must contain exactly one newline-terminated value")
    try:
        password = raw[:-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise SystemExit("BLOCKED: production support credential must be printable ASCII") from exc
    if not (PRODUCTION_SUPPORT_PASSWORD_MIN_LENGTH <= len(password) <= PRODUCTION_SUPPORT_PASSWORD_MAX_LENGTH):
        raise SystemExit("BLOCKED: production support credential length is outside policy")
    if any(ord(char) < 33 or ord(char) > 126 for char in password):
        raise SystemExit("BLOCKED: production support credential contains whitespace or control characters")
    classes = (
        bool(re.search(r"[a-z]", password)),
        bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"[0-9]", password)),
        bool(re.search(r"[^A-Za-z0-9]", password)),
    )
    if not all(classes):
        raise SystemExit("BLOCKED: production support credential must include four character classes")
    if len(set(password)) < PRODUCTION_SUPPORT_PASSWORD_MIN_UNIQUE_CHARS:
        raise SystemExit("BLOCKED: production support credential has insufficient symbol diversity")
    counts = Counter(password)
    symbol_distribution = -sum(
        (count / len(password)) * math.log2(count / len(password))
        for count in counts.values()
    )
    if symbol_distribution < PRODUCTION_SUPPORT_PASSWORD_MIN_SYMBOL_DISTRIBUTION:
        raise SystemExit("BLOCKED: production support credential symbol distribution is outside policy")
    for period in range(1, len(password) // 2 + 1):
        if password == (password[:period] * ((len(password) + period - 1) // period))[:len(password)]:
            raise SystemExit("BLOCKED: production support credential is a repeated pattern")
    return password


def validate_production_credential_provenance(path: Path, password: str) -> dict:
    raw = read_private_build_input(path, max_bytes=4096)
    if password.encode("ascii") in raw:
        raise SystemExit("BLOCKED: production credential provenance contains plaintext")
    try:
        provenance = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit("BLOCKED: production support credential provenance is invalid") from exc
    expected = {
        "schema": PRODUCTION_CREDENTIAL_PROVENANCE_SCHEMA,
        "generator": "python-secrets.token_urlsafe",
        "random_source": "os_csprng_via_python_secrets",
        "random_bytes": 48,
        "credential_length": len(password),
        "credential_sha256": hashlib.sha256(password.encode("ascii")).hexdigest(),
        "generator_file_sha256": base.file_sha256(PRODUCTION_CREDENTIAL_GENERATOR_SOURCE),
        "plaintext_embedded_in_provenance": False,
    }
    expected_keys = {*expected, "generated_at_utc"}
    if not isinstance(provenance, dict) or set(provenance) != expected_keys:
        raise SystemExit("BLOCKED: production credential provenance has unexpected fields")
    if any(provenance.get(key) != value for key, value in expected.items()):
        raise SystemExit("BLOCKED: production support credential provenance does not match the credential")
    try:
        generated_at = datetime.strptime(
            str(provenance["generated_at_utc"]),
            "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise SystemExit("BLOCKED: production support credential provenance timestamp is invalid") from exc
    if generated_at > datetime.now(timezone.utc):
        raise SystemExit("BLOCKED: production support credential provenance timestamp is invalid")
    return {
        "schema": provenance["schema"],
        "generator": provenance["generator"],
        "random_source": provenance["random_source"],
        "random_bytes": provenance["random_bytes"],
        "credential_length": provenance["credential_length"],
        "generator_file_sha256": provenance["generator_file_sha256"],
        "generated_at_utc": provenance["generated_at_utc"],
    }


def derive_production_root_password_hash(password: str, *, tag: str, repo_commit: str) -> tuple[str, dict]:
    if not PRODUCTION_OPENSSL.is_file() or not os.access(PRODUCTION_OPENSSL, os.X_OK):
        raise SystemExit("BLOCKED: pinned openssl is unavailable")
    if base.file_sha256(PRODUCTION_OPENSSL) != PRODUCTION_OPENSSL_SHA256:
        raise SystemExit("BLOCKED: pinned openssl hash mismatch")
    version = subprocess.run(
        [str(PRODUCTION_OPENSSL), "version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if version.returncode != 0 or not version.stdout.startswith(PRODUCTION_OPENSSL_VERSION_PREFIX):
        raise SystemExit("BLOCKED: pinned openssl version mismatch")
    salt = hashlib.sha256(f"dadooh-c18\0{tag}\0{repo_commit}".encode("utf-8")).hexdigest()[:16]
    result = subprocess.run(
        [str(PRODUCTION_OPENSSL), "passwd", "-6", "-salt", salt, "-stdin"],
        input=password + "\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    password_hash = result.stdout.strip()
    expected_pattern = rf"\$6\${re.escape(salt)}\$[./A-Za-z0-9]{{86}}"
    if result.returncode != 0 or not re.fullmatch(expected_pattern, password_hash):
        raise SystemExit("BLOCKED: failed to derive production root password hash")
    return password_hash, {
        "path": str(PRODUCTION_OPENSSL),
        "sha256": PRODUCTION_OPENSSL_SHA256,
        "version": version.stdout.strip(),
        "scheme": "sha512-crypt",
    }


def root_password_hash_from_shadow(shadow_text: str) -> str:
    root_lines = [line for line in shadow_text.splitlines() if line.startswith("root:")]
    if len(root_lines) != 1:
        raise SystemExit("BLOCKED: expected exactly one root account in /etc/shadow")
    fields = root_lines[0].split(":")
    if len(fields) != 9 or not fields[1]:
        raise SystemExit("BLOCKED: malformed root account in /etc/shadow")
    return fields[1]


def replace_root_password_hash(shadow_text: str, password_hash: str) -> str:
    root_password_hash_from_shadow(shadow_text)
    result = []
    replaced = 0
    for line in shadow_text.splitlines():
        if line.startswith("root:"):
            fields = line.split(":")
            fields[1] = password_hash
            line = ":".join(fields)
            replaced += 1
        result.append(line)
    if replaced != 1:
        raise SystemExit("BLOCKED: root password hash replacement was not unique")
    return "\n".join(result) + "\n"


def file_contains_bytes(path: Path, needle: bytes, *, chunk_size: int = 4 * 1024 * 1024) -> bool:
    if not needle:
        raise ValueError("needle must not be empty")
    overlap = len(needle) - 1
    tail = b""
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            candidate = tail + chunk
            if needle in candidate:
                return True
            tail = candidate[-overlap:] if overlap else b""
    return False


def git_text(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def repo_identity() -> dict:
    status = git_text("status", "--porcelain", "--untracked-files=all")
    return {
        "repo_commit": git_text("rev-parse", "HEAD"),
        "repo_tree": git_text("rev-parse", "HEAD^{tree}"),
        "repo_dirty": bool(status),
        "repo_dirty_entry_count": len([line for line in status.splitlines() if line.strip()]),
    }


def image_profile_for_tag(tag: str) -> str:
    if tag.startswith("c18-hwdecode-prod-"):
        return "production"
    return "lab"


def image_round_name(tag: str) -> str:
    profile = image_profile_for_tag(tag)
    if profile == "production":
        suffix = tag.removeprefix("c18-hwdecode-prod-")
        return f"C18.IMAGE-PROD.{suffix}"
    suffix = tag.removeprefix("c18-hwdecode-lab-")
    return f"C18.IMAGE-LAB.{suffix}"


def image_version_for_tag(tag: str) -> str:
    profile = image_profile_for_tag(tag)
    if profile == "production":
        suffix = tag.removeprefix("c18-hwdecode-prod-")
        return f"c18.image-prod.{suffix}"
    suffix = tag.removeprefix("c18-hwdecode-lab-")
    return f"c18.image-lab.{suffix}"


def source_declares_patch(source_data: dict, field: str, from_value: str, to_value: str) -> bool:
    for patch in source_data.get("patches", []):
        if not isinstance(patch, dict):
            continue
        if patch.get("field") == field and patch.get("from") == from_value and patch.get("to") == to_value:
            return True
    return False


def validate_player_runtime_snapshot(source_data: dict, kiosk_snapshot: str, kiosk_snapshot_sha: str) -> None:
    if source_data.get("snapshot", {}).get("sha256") != PLAYER_RUNTIME_KIOSK_SHA256:
        raise SystemExit("BLOCKED: player-runtime SOURCE.json snapshot sha mismatch")
    if kiosk_snapshot_sha != PLAYER_RUNTIME_KIOSK_SHA256:
        raise SystemExit(f"BLOCKED: player-runtime kiosk.py sha mismatch {kiosk_snapshot_sha}")
    for field, (from_value, to_value) in PLAYER_RUNTIME_REQUIRED_PATCHES.items():
        if not source_declares_patch(source_data, field, from_value, to_value):
            raise SystemExit(f"BLOCKED: player-runtime SOURCE.json missing required patch {field}")
    if MPV_PATH_NEW not in kiosk_snapshot or MPV_PATH_OLD in kiosk_snapshot:
        raise SystemExit("BLOCKED: player-runtime kiosk.py mpv_path governance mismatch")
    missing_tokens = [token for token in PLAYER_RUNTIME_TEARDOWN_TOKENS if token not in kiosk_snapshot]
    if missing_tokens:
        raise SystemExit("BLOCKED: player-runtime kiosk.py teardown governance mismatch")


def validate_player_runtime_baseline_package() -> dict:
    release_dir = REPO_ROOT / "releases" / "player-runtime" / PLAYER_RUNTIME_BASELINE_VERSION
    manifest_path = release_dir / f"dadooh-player-runtime-{PLAYER_RUNTIME_BASELINE_VERSION}.manifest.json"
    payload_path = release_dir / f"dadooh-player-runtime-{PLAYER_RUNTIME_BASELINE_VERSION}.tar.gz"
    release_gate_path = release_dir / "c18-player-runtime-release-gate.json"
    for path in (manifest_path, payload_path, release_gate_path):
        if not path.is_file():
            raise SystemExit(f"BLOCKED: player-runtime baseline artifact missing: {path}")
    expected_hashes = {
        manifest_path: PLAYER_RUNTIME_BASELINE_MANIFEST_SHA256,
        payload_path: PLAYER_RUNTIME_BASELINE_PAYLOAD_SHA256,
        release_gate_path: PLAYER_RUNTIME_BASELINE_RELEASE_GATE_SHA256,
    }
    for path, expected_sha in expected_hashes.items():
        actual_sha = base.file_sha256(path)
        if actual_sha != expected_sha:
            raise SystemExit(f"BLOCKED: player-runtime baseline artifact hash mismatch: {path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_manifest = {
        "component": "player-runtime",
        "version": PLAYER_RUNTIME_BASELINE_VERSION,
        "channel": "homologation",
        "source_commit": PLAYER_RUNTIME_BASELINE_SOURCE_COMMIT,
        "payload_sha256": PLAYER_RUNTIME_BASELINE_PAYLOAD_SHA256,
    }
    if any(manifest.get(key) != value for key, value in expected_manifest.items()):
        raise SystemExit("BLOCKED: player-runtime baseline manifest identity mismatch")
    features = set((manifest.get("requires") or {}).get("updater_features") or [])
    if "c25-player-surface-health-v1" not in features:
        raise SystemExit("BLOCKED: player-runtime baseline lacks C25 surface health contract")
    with tarfile.open(payload_path, "r:gz") as archive:
        try:
            payload_kiosk = archive.extractfile("kiosk.py")
        except KeyError as exc:
            raise SystemExit("BLOCKED: player-runtime baseline payload lacks kiosk.py") from exc
        if payload_kiosk is None or payload_kiosk.read() != PLAYER_RUNTIME_KIOSK.read_bytes():
            raise SystemExit("BLOCKED: image player snapshot differs from exact C25B payload")
    return {
        "version": PLAYER_RUNTIME_BASELINE_VERSION,
        "source_commit": PLAYER_RUNTIME_BASELINE_SOURCE_COMMIT,
        "payload_sha256": PLAYER_RUNTIME_BASELINE_PAYLOAD_SHA256,
        "manifest_sha256": PLAYER_RUNTIME_BASELINE_MANIFEST_SHA256,
        "release_gate_sha256": PLAYER_RUNTIME_BASELINE_RELEASE_GATE_SHA256,
        "kiosk_py_sha256": PLAYER_RUNTIME_KIOSK_SHA256,
    }


def deterministic_tree_sha256(root: Path) -> str:
    items: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            items.append({"path": relative, "type": "symlink", "target": os.readlink(path)})
        elif path.is_file():
            items.append({
                "path": relative,
                "type": "file",
                "size": path.stat().st_size,
                "sha256": base.file_sha256(path),
            })
    canonical = (json.dumps(items, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(canonical).hexdigest()


def validate_binary_build_inputs() -> dict[str, str]:
    actual = {
        "base_image_sha256": base.file_sha256(BASE_IMAGE),
        "hwdecode_bundle_sha256": deterministic_tree_sha256(BUNDLE),
        "ffmpeg_cli_sha256": base.file_sha256(FFMPEG_CLI),
    }
    expected = {
        "base_image_sha256": BASE_IMAGE_SHA256,
        "hwdecode_bundle_sha256": HWD_STACK_BUNDLE_SHA256,
        "ffmpeg_cli_sha256": FFMPEG_CLI_SHA256,
    }
    mismatches = [key for key in expected if actual.get(key) != expected[key]]
    if mismatches:
        raise SystemExit("BLOCKED: unrecognized binary image input: " + ",".join(mismatches))
    return actual


def production_seed_sensitive_fields(seed_data: dict) -> set[str]:
    fields = set(PRODUCTION_SEED_IDENTITY_FIELDS)
    for key in seed_data:
        lowered = str(key).lower()
        if (
            lowered.endswith("_token")
            or lowered.endswith("_password")
            or lowered.endswith("_secret")
            or lowered in {"token", "password", "secret"}
        ):
            fields.add(str(key))
    return fields


def production_identity_init_contract_valid(script_text: str) -> bool:
    return (
        "ssh-keygen -A" in script_text
        and "identity_complete" in script_text
        and "storage_contract=root_ext4_rw" in script_text
        and 'MARKER="${ROOT_PREFIX}/var/lib/dadooh/production-identity-initialized"'
        in script_text
    )


def validate_production_player_runtime_authorization() -> dict:
    try:
        auth = json.loads(PLAYER_RUNTIME_PRODUCTION_AUTH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"BLOCKED: production player-runtime authorization unreadable: {exc}") from exc
    version = str(auth.get("version") or "")
    if not version:
        raise SystemExit("BLOCKED: production player-runtime authorization missing version")
    release_dir = REPO_ROOT / "releases" / "player-runtime" / version
    manifest = release_dir / f"dadooh-player-runtime-{version}.manifest.json"
    payload = release_dir / f"dadooh-player-runtime-{version}.tar.gz"
    release_gate = release_dir / "c18-player-runtime-release-gate.json"
    cmd = [
        sys.executable,
        str(PLAYER_RUNTIME_PRODUCTION_AUTH_GATE),
        "--authorization",
        str(PLAYER_RUNTIME_PRODUCTION_AUTH),
        "--manifest",
        str(manifest),
        "--payload",
        str(payload),
        "--release-gate",
        str(release_gate),
        "--json",
    ]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    try:
        evidence = json.loads(result.stdout)
    except Exception as exc:
        raise SystemExit(
            "BLOCKED: production player-runtime authorization gate emitted invalid JSON: "
            f"{result.stderr[-1000:]}"
        ) from exc
    if result.returncode != 0 or evidence.get("passed") is not True:
        raise SystemExit(
            "BLOCKED: production player-runtime authorization gate failed: "
            + ",".join(str(item) for item in evidence.get("blockers", []))
        )
    return evidence


def validate_candidate_identity(tag: str, version: str, marker: str,
                                *, image_profile: str = "lab") -> None:
    suffix_pattern = r"[a-z0-9]+(?:-[a-z0-9]+)*"
    if image_profile == "production":
        match = re.fullmatch(rf"c18-hwdecode-prod-({suffix_pattern})", tag)
        profile_name = "prod"
    else:
        match = re.fullmatch(rf"c18-hwdecode-lab-({suffix_pattern})", tag)
        profile_name = "lab"
    if not match:
        raise SystemExit(f"BLOCKED: unsafe {image_profile} image tag {tag!r}")
    suffix = match.group(1)
    expected_version = f"c18.image-{profile_name}.{suffix}"
    expected_marker = f"/etc/dadooh/{tag}-image"
    if version != expected_version:
        raise SystemExit(
            f"BLOCKED: image version must match tag exactly; expected {expected_version!r}"
        )
    if marker != expected_marker:
        raise SystemExit(
            f"BLOCKED: image marker must match tag exactly; expected {expected_marker!r}"
        )
    if image_profile == "production" and (
        tag != PRODUCTION_TAG or version != PRODUCTION_VERSION or marker != PRODUCTION_MARKER
    ):
        raise SystemExit("BLOCKED: production candidate identity must match the pinned release")


def validate_image_bound_file(commit: str, relative_path: str) -> dict[str, str]:
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if ancestor.returncode != 0:
        raise SystemExit(f"BLOCKED: image-bound commit is not an ancestor of HEAD: {commit}")
    committed = subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    source = REPO_ROOT / relative_path
    if committed.returncode != 0 or not source.is_file():
        raise SystemExit(f"BLOCKED: image-bound source is unavailable: {commit}:{relative_path}")
    current = source.read_bytes()
    if committed.stdout != current:
        raise SystemExit(f"BLOCKED: image-bound source changed after {commit}: {relative_path}")
    return {
        "commit": commit,
        "path": relative_path,
        "sha256": hashlib.sha256(current).hexdigest(),
    }


def main():
    global TAG, VERSION, OUT_IMAGE, OUT_SHA, OUT_READY, MARKER
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--image-tag", help="explicit candidate image tag; defaults to current-golden.json")
    ap.add_argument("--image-version", help="explicit candidate image version; defaults from --image-tag")
    ap.add_argument("--image-marker", help="explicit candidate marker path; defaults to /etc/dadooh/<image-tag>-image")
    ap.add_argument("--image-profile", choices=("lab", "production"), default="lab")
    ap.add_argument("--totem-core-profile", choices=("homologation", "production"))
    ap.add_argument("--zerofree", help="zerofree executable required for production image hygiene")
    ap.add_argument(
        "--production-root-password-file",
        type=Path,
        help="external mode-0600 credential required for production images",
    )
    ap.add_argument(
        "--production-root-password-provenance-file",
        type=Path,
        help="external mode-0600 CSPRNG provenance required for the production credential",
    )
    ap.add_argument("--allow-dirty", action="store_true", help="allow exploratory builds from a dirty repo")
    args = ap.parse_args()
    totem_core_profile = args.totem_core_profile or (
        "production" if args.image_profile == "production" else "homologation"
    )
    if args.image_profile == "production" and totem_core_profile != "production":
        raise SystemExit("BLOCKED: production image requires totem-core production profile")
    if args.image_profile == "lab" and totem_core_profile == "production":
        raise SystemExit("BLOCKED: production totem-core profile requires --image-profile production")
    if args.image_profile == "lab" and (
        args.production_root_password_file or args.production_root_password_provenance_file
    ):
        raise SystemExit("BLOCKED: production root credential cannot be used by a lab image")
    repo = repo_identity()
    if args.image_profile == "production" and args.allow_dirty:
        raise SystemExit("BLOCKED: production images never allow dirty source trees")
    if repo["repo_dirty"] and (args.image_profile == "production" or not args.allow_dirty):
        raise SystemExit("BLOCKED: source repo dirty; commit first or pass --allow-dirty for exploratory builds")
    production_player_runtime_authorization = (
        validate_production_player_runtime_authorization()
        if args.image_profile == "production"
        else {"passed": "n/a", "result_claim": "not_required_for_homologation_image"}
    )
    production_playback_summary_provenance = (
        validate_image_bound_file(
            PRODUCTION_IMAGE_BOUND_PLAYBACK_SUMMARY_COMMIT,
            "scripts/board/c18_playback_health_summary.py",
        )
        if args.image_profile == "production"
        else {"commit": "n/a", "path": "n/a", "sha256": "n/a"}
    )
    zerofree_tool = resolve_zerofree(args.zerofree) if args.image_profile == "production" else None
    production_ext4_tools = (
        validate_production_ext4_tools()
        if args.image_profile == "production"
        else {"debugfs": {"path": shutil.which("debugfs") or "missing"}, "e2fsck": {"path": shutil.which("e2fsck") or "missing"}}
    )

    if args.image_tag:
        TAG = args.image_tag
        VERSION = args.image_version or image_version_for_tag(TAG)
        MARKER = args.image_marker or f"/etc/dadooh/{TAG}-image"
        validate_candidate_identity(TAG, VERSION, MARKER, image_profile=args.image_profile)
        OUT_IMAGE = ARM / (f"Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
                           f"6.12.58-{TAG}_minimal.img")
        OUT_SHA = Path(str(OUT_IMAGE) + ".sha256")
        OUT_READY = Path(str(OUT_IMAGE) + ".ready.json")
    elif args.image_profile == "production":
        TAG = PRODUCTION_TAG
        VERSION = PRODUCTION_VERSION
        MARKER = PRODUCTION_MARKER
        validate_candidate_identity(TAG, VERSION, MARKER, image_profile=args.image_profile)
        OUT_IMAGE = ARM / (f"Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
                           f"6.12.58-{TAG}_minimal.img")
        OUT_SHA = Path(str(OUT_IMAGE) + ".sha256")
        OUT_READY = Path(str(OUT_IMAGE) + ".ready.json")
    elif args.image_version or args.image_marker:
        raise SystemExit("BLOCKED: --image-version/--image-marker require --image-tag")
    round_name = image_round_name(TAG)

    production_root_password_hash = "n/a"
    production_root_password_tool = {"scheme": "n/a"}
    production_credential_provenance = {"schema": "n/a"}
    if args.image_profile == "production":
        if not args.production_root_password_file or not args.production_root_password_provenance_file:
            raise SystemExit("BLOCKED: production image requires credential and CSPRNG provenance files")
        support_password = load_production_support_password(args.production_root_password_file)
        production_credential_provenance = validate_production_credential_provenance(
            args.production_root_password_provenance_file,
            support_password,
        )
        production_root_password_hash, production_root_password_tool = (
            derive_production_root_password_hash(
                support_password,
                tag=TAG,
                repo_commit=repo["repo_commit"],
            )
        )
    else:
        support_password = ""

    log = []
    def L(m): print(m); log.append(m)

    # ---- preflight ----
    if not shutil.which("debugfs"):
        raise SystemExit("BLOCKED: debugfs_missing")
    for p in (
        BASE_IMAGE,
        BUNDLE / "mpv",
        BUNDLE / "lib",
        R4_UPDATECTL,
        PLAYER_RUNTIME_KIOSK,
        PLAYER_RUNTIME_SOURCE,
        PRODUCTION_IDENTITY_SCRIPT_SOURCE,
        PRODUCTION_IDENTITY_UNIT_SOURCE,
        PRODUCTION_SSH_DROPIN_SOURCE,
        PRODUCTION_CREDENTIAL_GENERATOR_SOURCE,
        PRODUCTION_SETTINGS_POLICY_SOURCE,
        PRODUCTION_OPEN_SETTINGS_UNIT_SOURCE,
    ):
        if not p.exists():
            raise SystemExit(f"BLOCKED: missing_input {p}")
    binary_build_inputs = validate_binary_build_inputs()
    if args.image_profile == "production":
        production_settings_unit_source = PRODUCTION_OPEN_SETTINGS_UNIT_SOURCE.read_text(encoding="utf-8")
        if (
            "totem_settings_production_apply_policy.py --write" not in production_settings_unit_source
            or "TOTEM_VISUAL_WIZARD_PAIRING_MODE=production" not in production_settings_unit_source
            or "totem_settings_lab_apply_policy" in production_settings_unit_source
            or "homologation" in production_settings_unit_source.lower()
        ):
            raise SystemExit("BLOCKED: production open-settings unit is not production-only")
        production_settings_policy_test = sh(
            [sys.executable, str(PRODUCTION_SETTINGS_POLICY_SOURCE), "--self-test"]
        )
        if production_settings_policy_test.returncode != 0:
            raise SystemExit("BLOCKED: production settings policy self-test failed")
        L(f"zerofree={zerofree_tool}")
    if OUT_IMAGE.exists() or OUT_SHA.exists() or OUT_READY.exists():
        if args.image_profile == "production" or not args.force:
            raise SystemExit(f"output exists (production never overwrites; lab may use --force): {OUT_IMAGE}")
    configured_out_dir = os.environ.get("C18_OUT_DIR")
    if args.image_profile == "production" and not configured_out_dir:
        raise SystemExit("BLOCKED: production build requires an explicit C18_OUT_DIR for evidence")
    configured_out_path = Path(configured_out_dir).expanduser().resolve() if configured_out_dir else None
    if args.image_profile == "production":
        assert configured_out_path is not None
        if configured_out_path.exists():
            raise SystemExit("BLOCKED: production evidence directory already exists")
        require_free_space(
            OUT_IMAGE.parent,
            PRODUCTION_OUTPUT_MIN_FREE_BYTES,
            label="production output filesystem",
        )
        wsl_host = Path("/mnt/c")
        if wsl_host.is_dir():
            require_free_space(
                wsl_host,
                PRODUCTION_WSL_HOST_MIN_FREE_BYTES,
                label="Windows host volume",
            )
    L(f"base_image={BASE_IMAGE.name}")
    L(f"out_image={OUT_IMAGE.name}")

    work = Path(tempfile.mkdtemp(prefix="c18-hwdecode-lab-"))
    out_dir = configured_out_path if configured_out_path is not None else work
    if args.image_profile == "production" and out_dir == work:
        raise SystemExit("BLOCKED: production evidence directory must be outside the ephemeral workdir")
    rootfs = work / "rootfs.ext4"
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=f".{OUT_IMAGE.name}.",
        suffix=".tmp",
        dir=OUT_IMAGE.parent,
    )
    os.close(tmp_fd)
    build_image = Path(tmp_name)
    build_sha = Path(str(build_image) + ".sha256")
    promotion_state = {
        "image_created": False,
        "sha_created": False,
        "ready_created": False,
        "evidence_complete": False,
    }

    def cleanup_temp_artifacts():
        for leftover in (build_sha, build_image):
            try:
                if leftover.exists():
                    leftover.unlink()
            except OSError as exc:
                print(f"WARN: failed to remove temp artifact {leftover}: {exc}", file=sys.stderr)
        if args.image_profile == "production" and not promotion_state["evidence_complete"]:
            if promotion_state["ready_created"]:
                OUT_READY.unlink(missing_ok=True)
            if promotion_state["sha_created"]:
                OUT_SHA.unlink(missing_ok=True)
            if promotion_state["image_created"]:
                OUT_IMAGE.unlink(missing_ok=True)
        if args.image_profile == "production":
            shutil.rmtree(work, ignore_errors=True)

    atexit.register(cleanup_temp_artifacts)

    # ---- copy base -> candidate, extract rootfs ----
    L("copy base image -> temp output ...")
    shutil.copy2(BASE_IMAGE, build_image)
    os.chmod(build_image, 0o600 if args.image_profile == "production" else 0o660)
    off, length = base.parse_mbr_linux_partition(build_image)
    L(f"linux partition offset={off} length={length}")
    base.copy_range(build_image, rootfs, offset=off, length=length)

    # ---- read image kiosk.py, then install the governed C18 player-runtime snapshot ----
    # Read via `debugfs dump` (binary-faithful: the file's exact bytes go to a local file,
    # debugfs's version banner goes to stderr — NOT into the content). NOTE: cat_file()
    # concatenates stdout+stderr, which appended the "debugfs 1.47.0 ..." banner to the file
    # in the defective build (c18-hwdecode-lab-1) → SyntaxError. Do NOT use cat for content.
    kiosk_orig = work / "kiosk_orig.py"
    base.debugfs(rootfs, f"dump {KIOSK} {kiosk_orig}")
    kiosk_src = kiosk_orig.read_text(encoding="utf-8") if kiosk_orig.exists() else ""
    if not kiosk_src or MPV_PATH_OLD not in kiosk_src:
        raise SystemExit(f"BLOCKED: kiosk.py mpv_path default not found for patch")
    n = kiosk_src.count(MPV_PATH_OLD)
    if n != 1:
        raise SystemExit(f"BLOCKED: kiosk.py mpv_path default occurs {n}x (expected 1)")
    kiosk_snapshot = PLAYER_RUNTIME_KIOSK.read_text(encoding="utf-8")
    kiosk_snapshot_sha = base.file_sha256(PLAYER_RUNTIME_KIOSK)
    source_data = json.loads(PLAYER_RUNTIME_SOURCE.read_text(encoding="utf-8"))
    validate_player_runtime_snapshot(source_data, kiosk_snapshot, kiosk_snapshot_sha)
    player_runtime_baseline = validate_player_runtime_baseline_package()
    kiosk_tmp = work / "kiosk.py"; kiosk_tmp.write_text(kiosk_snapshot, encoding="utf-8")

    production_known_private_residues: dict[str, bytes] = {}
    try:
        seed_raw = debugfs_read_bytes(rootfs, HOMOLOGATION_SEED)
        seed_data = json.loads(seed_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"BLOCKED: homologation seed invalid at {HOMOLOGATION_SEED}") from exc
    if not isinstance(seed_data, dict):
        raise SystemExit("BLOCKED: homologation seed root is not an object")
    if args.image_profile == "production":
        production_known_private_residues["homologation_seed_original"] = seed_raw
        for key in production_seed_sensitive_fields(seed_data):
            value = seed_data.get(key)
            if isinstance(value, str) and value:
                production_known_private_residues[f"seed_field:{key}"] = value.encode("utf-8")
    seed_data["mpv_path"] = WRAPPER
    if args.image_profile == "production":
        for key in production_seed_sensitive_fields(seed_data):
            if key in seed_data:
                seed_data[key] = ""
    seed_tmp = work / "private-values.seed.json"
    seed_tmp.write_text(json.dumps(seed_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    production_armbian_env_tmp = work / "armbianEnv.production.txt"
    production_armbian_firstrun_tmp = work / "armbian-firstrun.production"
    kiosky_commit_tmp = work / ".kiosky_player_commit"
    production_shadow_entries: dict[str, dict] = {}
    production_base_root_password_hashes: set[str] = set()
    if args.image_profile == "production":
        for host_key_path in PRODUCTION_EMBEDDED_SSH_HOST_KEYS:
            if base.stat_file(rootfs, host_key_path).get("present"):
                production_known_private_residues[f"ssh_host_key:{host_key_path}"] = (
                    debugfs_read_bytes(rootfs, host_key_path)
                )
        try:
            production_armbian_env_original = debugfs_read_bytes(
                rootfs,
                PRODUCTION_ARMBIAN_ENV,
            ).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SystemExit(f"BLOCKED: production boot environment invalid at {PRODUCTION_ARMBIAN_ENV}") from exc
        production_armbian_env_tmp.write_text(
            sanitize_production_armbian_env(production_armbian_env_original),
            encoding="utf-8",
        )
        try:
            production_armbian_firstrun_original = debugfs_read_bytes(
                rootfs,
                PRODUCTION_ARMBIAN_FIRSTRUN_CONFIG,
            ).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SystemExit(
                f"BLOCKED: Armbian first-run configuration invalid at "
                f"{PRODUCTION_ARMBIAN_FIRSTRUN_CONFIG}"
            ) from exc
        production_armbian_firstrun_tmp.write_text(
            sanitize_production_armbian_firstrun(production_armbian_firstrun_original),
            encoding="utf-8",
        )
        kiosky_commit_tmp.write_text(PLAYER_RUNTIME_BASELINE_SOURCE_COMMIT + "\n", encoding="utf-8")
        for index, shadow_path in enumerate(PRODUCTION_SHADOW_PATHS):
            shadow_stat = base.stat_file(rootfs, shadow_path)
            if not shadow_stat.get("present"):
                raise SystemExit(f"BLOCKED: production base image lacks {shadow_path}")
            if shadow_stat.get("uid") != 0 or "gid" not in shadow_stat or "mode" not in shadow_stat:
                raise SystemExit(f"BLOCKED: production base image ownership is invalid for {shadow_path}")
            shadow_mode = int(shadow_stat["mode"]) & 0o777
            shadow_gid = int(shadow_stat["gid"])
            if shadow_mode not in (0o600, 0o640):
                raise SystemExit(f"BLOCKED: production base image mode is outside policy for {shadow_path}")
            try:
                shadow_text = debugfs_read_bytes(rootfs, shadow_path).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SystemExit(f"BLOCKED: invalid encoding in {shadow_path}") from exc
            old_root_hash = root_password_hash_from_shadow(shadow_text)
            if hmac.compare_digest(old_root_hash, production_root_password_hash):
                raise SystemExit(f"BLOCKED: production root password hash was not rotated in {shadow_path}")
            shadow_tmp = work / f"shadow.production.{index}"
            shadow_tmp.write_text(
                replace_root_password_hash(shadow_text, production_root_password_hash),
                encoding="utf-8",
            )
            os.chmod(shadow_tmp, 0o600)
            production_shadow_entries[shadow_path] = {
                "tmp": shadow_tmp,
                "mode": shadow_mode,
                "gid": shadow_gid,
            }
            production_base_root_password_hashes.add(old_root_hash)

    # ---- wrapper + marker temp files ----
    wrap_tmp = work / "totem-mpv-hwdecode"; wrap_tmp.write_text(WRAPPER_SH, encoding="utf-8")
    marker_tmp = work / "marker"
    marker_scope_lines = (
        [
            "artifact_private=false", "final_image=true",
            "production_image=true",
        ]
        if args.image_profile == "production"
        else [
            "artifact_private=true", "final_image=false",
            "not_for_production=true", "not_for_distribution=true",
        ]
    )
    marker_tmp.write_text("\n".join([
        f"image_tag={TAG}", f"image_version={VERSION}",
        *marker_scope_lines,
        "base_image_line=c17.4.2", "c17_7_used_as_base=false",
        "kernel_touched=false", "u_boot_touched=false", "dtb_touched=false",
        f"c12_readonly_touched={str(args.image_profile == 'production').lower()}",
        f"c12_readonly_blocked={str(args.image_profile == 'production').lower()}",
        f"production_rootfs_mode={'ext4_rw' if args.image_profile == 'production' else 'n/a'}",
        f"production_overlayroot_disabled={str(args.image_profile == 'production').lower()}",
        "hwdecode_stack=cedrus_v4l2request",
        f"ffmpeg={SOURCES['ffmpeg_source']}@{SOURCES['ffmpeg_commit']}",
        f"mpv={SOURCES['mpv_source']}@{SOURCES['mpv_commit']}",
        f"libplacebo@{SOURCES['libplacebo_commit']}",
        "player_hwdec=v4l2request-copy vo=gpu gpu_context=drm",
        "r4_updater_perms=injected",
        "totem_core_current_embedded=true",
        f"totem_core_current_version={totem_core_image_embed.TOTEM_CORE_VERSION}",
        f"totem_core_embed_profile={totem_core_profile}",
        "totem_update_policy_embedded=true",
        f"totem_update_timer_enabled={str(totem_core_profile == 'production').lower()}",
        "player_runtime_launcher_fixed_by_image=true",
        "player_runtime_verified_marker_required=true",
        f"player_runtime_baseline_version={PLAYER_RUNTIME_BASELINE_VERSION}",
        f"player_runtime_baseline_payload_sha256={PLAYER_RUNTIME_BASELINE_PAYLOAD_SHA256}",
        "c25_visible_product_states_embedded=true",
        f"base_image_sha256={binary_build_inputs['base_image_sha256']}",
        f"hwdecode_bundle_sha256={binary_build_inputs['hwdecode_bundle_sha256']}",
        "player_runtime_reconcile_available=true",
        "player_runtime_lab_thaw_guard=true",
        "player_runtime_gate_semantic_mpv_args=true",
        "player_runtime_boot_state_evidence_gate=true",
        "player_runtime_fault_injection_gate=true",
        "player_runtime_reconcile_corrupt_state_fail_closed=true",
        "player_runtime_ota_still_frozen=true",
        f"playback_health_summary_commit={PRODUCTION_IMAGE_BOUND_PLAYBACK_SUMMARY_COMMIT}",
        "totem_core_excludes_kiosky_service_launcher=true",
        f"player_runtime_kiosk_source={PLAYER_RUNTIME_KIOSK.relative_to(REPO_ROOT)}",
        f"player_runtime_kiosk_sha256={kiosk_snapshot_sha}",
        "homologation_seed_mpv_path=totem-mpv-hwdecode",
        f"production_private_lab_inputs_removed={str(args.image_profile == 'production').lower()}",
        f"production_free_space_zeroed={str(args.image_profile == 'production').lower()}",
        f"production_ssh_host_keys_generated_on_device={str(args.image_profile == 'production').lower()}",
        f"production_armbian_host_key_regeneration_disabled={str(args.image_profile == 'production').lower()}",
        f"production_rootfs_auto_expand_enabled={str(args.image_profile == 'production').lower()}",
        f"production_shared_support_credential_rotated={str(args.image_profile == 'production').lower()}",
        f"production_support_credential_csprng_provenance={str(args.image_profile == 'production').lower()}",
        f"production_per_device_credentials_pending={str(args.image_profile == 'production').lower()}",
        f"production_settings_policy_embedded={str(args.image_profile == 'production').lower()}",
        f"production_lab_settings_policy_removed={str(args.image_profile == 'production').lower()}",
        "panfrost_rebind_service=installed",
        "c17_4_trace_dir=/run/totem/c17-4-firstboot",
        "supersedes=c18-hwdecode-lab-1 (kiosk.py banner SyntaxError) & 1b (--no-osc fatal on no-Lua mpv) & 1c (zero-copy panfrost js faults on portrait media) & 1d (playback stable, totem-core OTA layout missing from image) & 1g (player launcher still inside totem-core boundary) & 1h (homologation seed reset mpv_path to stock mpv) & 1i (player-runtime path still split from launcher default) & 1j (golden delivery, before player-runtime thaw foundation) & 1l (golden delivery, before post-audit deep-health/freeze/docs lock) & 1n (golden delivery before guarded reconcile/evidence-gate hardening) & 1o (golden delivery before audit-ready persistent /data trial tooling) & 1p (boot reconcile ran as totem, so /data/player-runtime hygiene was non-effective) & 1q (golden delivery before multi-segment deep-health gate and persistent-trial abort cleanup) & 1r (golden delivery before cold-boot/power-loss pre-hardening gates) & 1s (golden delivery before boot-state evidence and crash-boundary gates) & 1t (golden delivery before post-M6 reconcile freeze hardware proof) & 1u (golden delivery before physical power-loss/soak/server-side gates)",
        "hardware_validation_required=true",
    ]) + "\n", encoding="utf-8")

    # panfrost rebind service + script temp files
    panfrost_sh_tmp = work / "totem-panfrost-rebind.sh"; panfrost_sh_tmp.write_text(PANFROST_SH_BODY, encoding="utf-8")
    panfrost_unit_tmp = work / "totem-panfrost-rebind.service"; panfrost_unit_tmp.write_text(PANFROST_UNIT_BODY, encoding="utf-8")
    stability_dropin_tmp = work / "30-c18-stability.conf"; stability_dropin_tmp.write_text(C18_STABILITY_DROPIN_BODY, encoding="utf-8")

    # ---- build the debugfs command batch (rootless ext4 edit) ----
    cmds = []
    for d in (HWDIR, f"{HWDIR}/bin", f"{HWDIR}/lib"):
        cmds += [f"mkdir {d}", f"set_inode_field {d} mode 040755",
                 f"set_inode_field {d} uid 0", f"set_inode_field {d} gid 0"]

    def put(local, target, mode):
        cmds.append(f"rm {target}")  # harmless if absent
        cmds.append(f"write {local} {target}")
        cmds.append(f"set_inode_field {target} mode {base.mode_with_type(mode)}")
        cmds.append(f"set_inode_field {target} uid 0")
        cmds.append(f"set_inode_field {target} gid 0")

    # stack binaries
    put(str(BUNDLE / "mpv"), f"{HWDIR}/bin/mpv", "0755")
    ffmpeg_included = FFMPEG_CLI.exists()
    if ffmpeg_included:
        put(str(FFMPEG_CLI), f"{HWDIR}/bin/ffmpeg", "0755")

    # stack libs: real files first, then symlinks
    libdir = BUNDLE / "lib"
    real_files, symlinks = [], []
    for entry in sorted(os.listdir(libdir)):
        p = libdir / entry
        (symlinks if p.is_symlink() else real_files).append(entry)
    for entry in real_files:
        put(str(libdir / entry), f"{HWDIR}/lib/{entry}", "0755")
    for entry in symlinks:
        tgt = os.readlink(libdir / entry)
        if "/" in entry or entry.startswith(".") or os.path.isabs(tgt) or ".." in Path(tgt).parts:
            raise SystemExit(f"BLOCKED: unsafe stack lib symlink {entry!r}->{tgt!r}")
        cmds.append(f"rm {HWDIR}/lib/{entry}")
        cmds.append(f"symlink {HWDIR}/lib/{entry} {tgt}")

    # wrapper, patched kiosk.py, R4 updatectl, marker
    put(str(wrap_tmp), WRAPPER, "0755")
    put(str(kiosk_tmp), KIOSK, "0644")
    put(str(R4_UPDATECTL), UPDATECTL, "0755")
    put(str(seed_tmp), HOMOLOGATION_SEED, "0600")
    put(str(marker_tmp), MARKER, "0644")
    # panfrost rebind service (oneshot, before kiosky-player) + enable symlink
    put(str(panfrost_sh_tmp), PANFROST_SH, "0755")
    put(str(panfrost_unit_tmp), PANFROST_UNIT, "0644")
    cmds.append(f"symlink {PANFROST_WANTS} {PANFROST_UNIT}")
    put(str(stability_dropin_tmp), C18_STABILITY_DROPIN, "0644")
    if args.image_profile == "production":
        cmds += [
            "mkdir /etc/systemd/system/ssh.service.d",
            "set_inode_field /etc/systemd/system/ssh.service.d mode 040755",
            "set_inode_field /etc/systemd/system/ssh.service.d uid 0",
            "set_inode_field /etc/systemd/system/ssh.service.d gid 0",
        ]
        put(str(PRODUCTION_IDENTITY_SCRIPT_SOURCE), PRODUCTION_IDENTITY_SCRIPT, "0755")
        put(str(PRODUCTION_IDENTITY_UNIT_SOURCE), PRODUCTION_IDENTITY_UNIT, "0644")
        put(str(PRODUCTION_SSH_DROPIN_SOURCE), PRODUCTION_SSH_DROPIN, "0644")
        put(str(PRODUCTION_OPEN_SETTINGS_UNIT_SOURCE), PRODUCTION_OPEN_SETTINGS_UNIT, "0644")
        put(str(production_armbian_env_tmp), PRODUCTION_ARMBIAN_ENV, "0644")
        put(
            str(production_armbian_firstrun_tmp),
            PRODUCTION_ARMBIAN_FIRSTRUN_CONFIG,
            "0644",
        )
        put(str(kiosky_commit_tmp), KIOSKY_PLAYER_COMMIT_MARKER, "0644")
        for shadow_path, shadow_entry in production_shadow_entries.items():
            put(str(shadow_entry["tmp"]), shadow_path, f"{shadow_entry['mode']:04o}")
            cmds.append(f"set_inode_field {shadow_path} gid {shadow_entry['gid']}")
        cmds.append(f"rm {PRODUCTION_IDENTITY_WANTS}")
        cmds.append(f"symlink {PRODUCTION_IDENTITY_WANTS} {PRODUCTION_IDENTITY_UNIT}")
        for path in (
            *PRODUCTION_FORBIDDEN_LAB_PATHS,
            *PRODUCTION_EMBEDDED_SSH_HOST_KEYS,
            *PRODUCTION_OVERLAYROOT_PATHS,
        ):
            cmds.append(f"rm {path}")
        cmds.append("rmdir /data/state/totem-read-only-image-lab")

    L(f"debugfs commands: {len(cmds)} (stack libs real={len(real_files)} symlink={len(symlinks)})")
    out = (
        run_debugfs_batch_strict(rootfs, cmds, work)
        if args.image_profile == "production"
        else base.debugfs_batch(rootfs, cmds, work)
    )
    for shadow_entry in production_shadow_entries.values():
        shadow_tmp = shadow_entry["tmp"]
        if shadow_tmp.exists():
            shadow_tmp.write_bytes(b"\0" * shadow_tmp.stat().st_size)
            shadow_tmp.unlink()
    if args.image_profile != "production":
        bad = [ln for ln in out.splitlines() if "rror" in ln.lower() and "Errno 2" not in ln
               and "while trying to delete" not in ln.lower()]
        if bad:
            L("debugfs stderr (filtered):")
            for ln in bad[:30]:
                L("  " + ln)
            raise SystemExit("BLOCKED: unexpected debugfs errors while deriving image")

    # ---- embed OTA-ready totem-core current/fallback/wrapper layout ----
    totem_core_embed = totem_core_image_embed.write_totem_core_embed(
        rootfs,
        work,
        REPO_ROOT,
        profile=totem_core_profile,
        debugfs_batch_runner=(
            run_debugfs_batch_strict if args.image_profile == "production" else None
        ),
    )
    L(
        "totem-core embedded "
        f"version={totem_core_embed['totem_core_current_version']} "
        f"files={totem_core_embed['totem_core_files_embedded']}"
    )

    # ---- filesystem consistency and production free-space hygiene ----
    e2fsck_tool = PRODUCTION_E2FSCK if args.image_profile == "production" else Path("e2fsck")
    fsck_prepare = sh([str(e2fsck_tool), "-f", "-p", str(rootfs)])
    if fsck_prepare.returncode not in (0, 1):
        raise SystemExit(f"BLOCKED: e2fsck preparation failed rc={fsck_prepare.returncode}")
    L(f"e2fsck preparation rc={fsck_prepare.returncode}")
    if fsck_prepare.stdout.strip():
        L("e2fsck preparation output:\n" + fsck_prepare.stdout.strip())

    zerofree_summary = "n/a"
    zerofree_tool_sha256 = "n/a"
    if args.image_profile == "production":
        assert zerofree_tool is not None
        zerofree_tool_sha256 = base.file_sha256(zerofree_tool)
        scrub = sh([str(zerofree_tool), str(rootfs)])
        if scrub.returncode != 0:
            raise SystemExit(f"BLOCKED: zerofree failed rc={scrub.returncode}")
        scrub_scan, zerofree_summary = run_zerofree_scan(zerofree_tool, rootfs)
        if scrub_scan.returncode != 0 or not zerofree_summary.startswith("0/"):
            raise SystemExit(
                "BLOCKED: ext4 free-space verification failed: "
                f"rc={scrub_scan.returncode} summary={zerofree_summary!r}"
            )
        L(f"zerofree verification={zerofree_summary}")

    fsck = sh([str(e2fsck_tool), "-f", "-n", str(rootfs)])
    fsck_clean = fsck.returncode == 0
    if not fsck_clean:
        raise SystemExit(f"BLOCKED: final e2fsck failed rc={fsck.returncode}")
    L("e2fsck rc=0 (clean)")

    # ---- write rootfs back into the image ----
    base.write_range(build_image, rootfs, offset=off)
    L("rootfs written back into temp output image")

    production_root_password_plaintext_absent = "n/a"
    production_old_root_password_hashes_absent = "n/a"
    production_known_private_residues_absent = "n/a"
    if args.image_profile == "production":
        production_root_password_plaintext_absent = not file_contains_bytes(
            build_image,
            support_password.encode("ascii"),
        )
        support_password = ""
        if not production_root_password_plaintext_absent:
            raise SystemExit("BLOCKED: production support credential plaintext found in image bytes")
        production_old_root_password_hashes_absent = all(
            not file_contains_bytes(build_image, old_hash.encode("ascii"))
            for old_hash in production_base_root_password_hashes
        )
        if not production_old_root_password_hashes_absent:
            raise SystemExit("BLOCKED: inherited root password verifier survived in image bytes")
        production_known_private_residues_absent = all(
            not file_contains_bytes(build_image, payload)
            for payload in production_known_private_residues.values()
            if payload
        )
        if not production_known_private_residues_absent:
            raise SystemExit("BLOCKED: known private base-image residue survived in image bytes")
        production_base_root_password_hashes.clear()
        production_known_private_residues.clear()
        L("production support credential plaintext scan=absent")
        L("inherited root password verifier scan=absent")
        L("known private base-image residue scan=absent")

    # ---- candidate sha256 (do not publish .sha256 before validation passes) ----
    sha = base.file_sha256(build_image)
    L(f"sha256={sha}")

    # ---- offline validation: re-extract candidate image, verify via debugfs ----
    off2, len2 = base.parse_mbr_linux_partition(build_image)
    vroot = work / "verify.ext4"
    base.copy_range(build_image, vroot, offset=off2, length=len2)

    def present(path):
        return base.stat_file(vroot, path).get("present", False)
    def execu(path):
        return bool(base.stat_file(vroot, path).get("mode", 0) & 0o111)

    grp = base.cat_file(vroot, "/etc/group") or ""
    video_line = next((ln for ln in grp.splitlines() if ln.startswith("video:")), "")
    wrap_now = base.cat_file(vroot, WRAPPER) or ""
    upd_now = base.cat_file(vroot, UPDATECTL) or ""
    marker_now = base.cat_file(vroot, MARKER) or ""
    panfrost_unit_now = base.cat_file(vroot, PANFROST_UNIT) or ""
    service_launcher_now = base.cat_file(vroot, "/opt/totem/bin/kiosky_service_launcher.sh") or ""
    totem_launcher_now = base.cat_file(vroot, "/opt/totem/bin/totem-kiosky-launcher.sh") or ""
    kiosky_dropin_now = base.cat_file(vroot, "/etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf") or ""
    try:
        seed_verify = json.loads(debugfs_read_bytes(vroot, HOMOLOGATION_SEED).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        seed_verify = {}
    machine_id_verify = debugfs_read_bytes(vroot, "/etc/machine-id", allow_empty=True)
    production_identity_script_now = base.cat_file(vroot, PRODUCTION_IDENTITY_SCRIPT) or ""
    production_identity_unit_now = base.cat_file(vroot, PRODUCTION_IDENTITY_UNIT) or ""
    production_ssh_dropin_now = base.cat_file(vroot, PRODUCTION_SSH_DROPIN) or ""
    production_open_settings_unit_now = base.cat_file(vroot, PRODUCTION_OPEN_SETTINGS_UNIT) or ""
    production_armbian_env_now = base.cat_file(vroot, PRODUCTION_ARMBIAN_ENV) or ""
    production_armbian_firstrun_config_now = (
        base.cat_file(vroot, PRODUCTION_ARMBIAN_FIRSTRUN_CONFIG) or ""
    )
    production_armbian_firstrun_script_now = (
        base.cat_file(vroot, PRODUCTION_ARMBIAN_FIRSTRUN_SCRIPT) or ""
    )
    production_armbian_firstrun_unit_now = (
        base.cat_file(vroot, PRODUCTION_ARMBIAN_FIRSTRUN_UNIT) or ""
    )
    production_armbian_firstrun_wants_stat = base.stat_file(
        vroot,
        PRODUCTION_ARMBIAN_FIRSTRUN_WANTS,
    )
    production_armbian_firstrun_wants_target = debugfs_fast_symlink_target(
        vroot,
        PRODUCTION_ARMBIAN_FIRSTRUN_WANTS,
    )
    production_rootfs_resize_unit_now = (
        base.cat_file(vroot, PRODUCTION_ROOTFS_RESIZE_UNIT) or ""
    )
    production_rootfs_resize_wants_stat = base.stat_file(
        vroot,
        PRODUCTION_ROOTFS_RESIZE_WANTS,
    )
    production_rootfs_resize_wants_target = debugfs_fast_symlink_target(
        vroot,
        PRODUCTION_ROOTFS_RESIZE_WANTS,
    )
    kiosky_commit_verify_file = work / "kiosky-player-commit.verify"
    base.debugfs(vroot, f"dump {KIOSKY_PLAYER_COMMIT_MARKER} {kiosky_commit_verify_file}")
    kiosky_commit_marker_now = (
        kiosky_commit_verify_file.read_text(encoding="utf-8").strip()
        if kiosky_commit_verify_file.is_file()
        else ""
    )
    production_root_password_hashes_now: dict[str, str] = {}
    production_shadow_stats_now: dict[str, dict] = {}
    if args.image_profile == "production":
        for shadow_path in PRODUCTION_SHADOW_PATHS:
            try:
                shadow_text_now = debugfs_read_bytes(vroot, shadow_path).decode("utf-8")
                production_root_password_hashes_now[shadow_path] = root_password_hash_from_shadow(
                    shadow_text_now
                )
            except UnicodeDecodeError:
                production_root_password_hashes_now[shadow_path] = ""
            production_shadow_stats_now[shadow_path] = base.stat_file(vroot, shadow_path)
    verify_zerofree_summary = "n/a"
    verify_free_space_zeroed = "n/a"
    if args.image_profile == "production":
        assert zerofree_tool is not None
        verify_scrub_scan, verify_zerofree_summary = run_zerofree_scan(zerofree_tool, vroot)
        verify_free_space_zeroed = (
            verify_scrub_scan.returncode == 0 and verify_zerofree_summary.startswith("0/")
        )
    totem_core_validation = totem_core_image_embed.validate_totem_core_embed(vroot, profile=totem_core_profile)
    libs_present = {e: present(f"{HWDIR}/lib/{e}") for e in real_files}
    player_runtime_gate = sh([
        sys.executable,
        str(REPO_ROOT / "scripts/qa/c18_player_runtime_release_gate.py"),
        "--self-test",
    ])
    player_runtime_sandbox = sh([
        sys.executable,
        str(REPO_ROOT / "scripts/sim/run_player_runtime_sandbox.py"),
        "--json",
    ])
    sandbox_json_start = player_runtime_sandbox.stdout.find("{")
    try:
        player_runtime_sandbox_json = json.loads(player_runtime_sandbox.stdout[sandbox_json_start:]) if sandbox_json_start >= 0 else {}
    except json.JSONDecodeError:
        player_runtime_sandbox_json = {}
    if player_runtime_gate.returncode != 0:
        L("player-runtime release gate FAILED:")
        L(player_runtime_gate.stdout[-2000:])
    if player_runtime_sandbox.returncode != 0 or player_runtime_sandbox_json.get("passed") is not True:
        L("player-runtime sandbox FAILED:")
        L(player_runtime_sandbox.stdout[-2000:])

    # py_compile the patched kiosk.py from the FINAL image via a clean dump (the missing
    # check that let the defective v1 ship — cat-read had the banner; v1's file did not compile)
    import py_compile as _pyc
    kverify = work / "kiosk_verify.py"
    base.debugfs(vroot, f"dump {KIOSK} {kverify}")
    kiosk_clean = kverify.read_text(encoding="utf-8", errors="replace") if kverify.exists() else ""
    try:
        _pyc.compile(str(kverify), doraise=True); kiosk_compiles = True
    except Exception as e:
        kiosk_compiles = False; L(f"kiosk.py compile FAILED: {e}")

    v = {
        "custom_mpv_installed": present(f"{HWDIR}/bin/mpv") and execu(f"{HWDIR}/bin/mpv"),
        "custom_ffmpeg_installed": present(f"{HWDIR}/bin/ffmpeg") if ffmpeg_included else "n/a",
        "system_ffmpeg_present": present(C25_SYSTEM_FFMPEG) and execu(C25_SYSTEM_FFMPEG),
        "system_ffprobe_present": present(C25_SYSTEM_FFPROBE) and execu(C25_SYSTEM_FFPROBE),
        "c25_surface_fonts_present": all(present(path) for path in C25_SURFACE_FONTS),
        "all_stack_libs_present": all(libs_present.values()),
        "wrapper_present": present(WRAPPER) and execu(WRAPPER),
        "wrapper_forces_hwdec": "--hwdec=v4l2request-copy" in wrap_now and "--vo=gpu" in wrap_now
                                and "--gpu-context=drm" in wrap_now and "LD_LIBRARY_PATH" in wrap_now,
        "wrapper_strips_no_osc": "--no-osc) continue" in wrap_now,
        "player_points_to_wrapper": MPV_PATH_NEW in kiosk_clean,
        "player_no_longer_default_mpv": MPV_PATH_OLD not in kiosk_clean,
        "kiosk_py_compiles": kiosk_compiles,
        "settings_restore_timeout_present": present("/usr/bin/timeout") and execu("/usr/bin/timeout"),
        "panfrost_rebind_script_present": present(PANFROST_SH) and execu(PANFROST_SH),
        "panfrost_rebind_unit_present": present(PANFROST_UNIT),
        "panfrost_rebind_enabled": present(PANFROST_WANTS),
        "panfrost_unit_before_player": "Before=kiosky-player.service" in panfrost_unit_now,
        "kiosky_service_routes_through_totem_launcher": (
            "ExecStart=" in kiosky_dropin_now
            and "ExecStart=/usr/bin/env bash /opt/totem/bin/totem-kiosky-launcher.sh" in kiosky_dropin_now
        ),
        "kiosky_service_launcher_waits_for_child_shutdown": (
            "wait_child_after_stop()" in service_launcher_now
            and "shutdown_waiting_for_child" in service_launcher_now
            and "shutdown_child_exited" in service_launcher_now
            and 'wait_child_after_stop "$child_pid" "$rc"' in service_launcher_now
        ),
        "kiosky_service_reconciles_player_runtime_state": (
            "C18_PLAYER_RUNTIME_RECONCILE=1" in kiosky_dropin_now
            and "--allow-player-runtime-maintenance" in kiosky_dropin_now
            and "reconcile --component player-runtime" in kiosky_dropin_now
            and "ExecStartPre=-+/usr/bin/env C18_PLAYER_RUNTIME_RECONCILE=1" in kiosky_dropin_now
            and "prefixed with `+`" in kiosky_dropin_now
            and "while reconcile must manage /data/player-runtime" in kiosky_dropin_now
            and "root-owned state" in kiosky_dropin_now
            and "RequiresMountsFor=/data" in kiosky_dropin_now
            and "After=local-fs.target" in kiosky_dropin_now
            and "KillMode=mixed" in kiosky_dropin_now
            and "TimeoutStopSec=90s" in kiosky_dropin_now
            and "SendSIGKILL=yes" in kiosky_dropin_now
            and "mpv to quit over IPC before falling back" in kiosky_dropin_now
            and "KillMode=control-group" not in kiosky_dropin_now
            and "ExecStartPre=-/usr/bin/env C18_PLAYER_RUNTIME_RECONCILE=1" not in kiosky_dropin_now
        ),
        "totem_kiosky_launcher_uses_player_runtime_path": (
            "/data/player-runtime/current" in totem_launcher_now
            and "/data/apps/kiosky-player/current" not in totem_launcher_now
        ),
        "totem_kiosky_launcher_requires_verified_marker": (
            ".release_verified.json" in totem_launcher_now
            and "kiosk_py_sha256" in totem_launcher_now
            and "tree_sha256" in totem_launcher_now
            and "deep_health_not_passed" in totem_launcher_now
            and "quarantined" in totem_launcher_now
            and "FALLBACK_APP_DIR" in totem_launcher_now
        ),
        "c17_4_trace_moved_to_run": present(C18_STABILITY_DROPIN),
        "r4_updater_perms_present": "_make_world_traversable" in upd_now,
        "player_runtime_updatectl_marker_schema": "dadooh.c18.player_runtime.verified.v1" in upd_now,
        "player_runtime_updatectl_primitives_present": (
            "def _apply_player_runtime_from_manifest_path_unfrozen" in upd_now
            and "def _write_player_runtime_marker" in upd_now
            and "def _validate_player_runtime_marker" in upd_now
            and "def _quarantine_player_runtime_identity" in upd_now
            and "health did not observe candidate kiosk.py identity" in upd_now
            and "health did not observe candidate tree identity" in upd_now
        ),
        "player_runtime_updatectl_reconcile_available": (
            "def _reconcile_player_runtime_state" in upd_now
            and '"reconcile": cmd_reconcile' in upd_now
        ),
        "player_runtime_lab_thaw_guard_present": (
            "PLAYER_RUNTIME_LAB_THAW_ENABLED = False" in upd_now
            and "requires explicit lab thaw guard" in upd_now
        ),
        "player_runtime_ota_still_frozen": (
            '"player-runtime": "player-runtime OTA is frozen' in upd_now
            and "return 44" in upd_now
        ),
        "player_runtime_release_gate_passed": player_runtime_gate.returncode == 0,
        "player_runtime_sandbox_passed": (
            player_runtime_sandbox.returncode == 0
            and player_runtime_sandbox_json.get("passed") is True
            and player_runtime_sandbox_json.get("checks", {}).get("cli_apply_still_frozen") is True
            and player_runtime_sandbox_json.get("checks", {}).get("failed_apply_without_previous_falls_back_to_image") is True
            and player_runtime_sandbox_json.get("checks", {}).get("launcher_unmarked_data_current_falls_back") is True
            and player_runtime_sandbox_json.get("checks", {}).get("reconcile_candidate_rejected_hygiene_passed") is True
        ),
        "totem_core_ota_ready": totem_core_validation["ok"],
        "totem_in_video_group": "totem" in video_line.split(":")[-1].split(","),
        "marker_present": present(MARKER),
        "marker_scope_matches_profile": (
            (
                "final_image=true" in marker_now
                and "production_image=true" in marker_now
                and "artifact_private=false" in marker_now
                and "not_for_production" not in marker_now
                and "not_for_distribution" not in marker_now
            )
            if args.image_profile == "production"
            else (
                "final_image=false" in marker_now
                and "not_for_production=true" in marker_now
            )
        ),
        "homologation_seed_mpv_path_points_to_wrapper": seed_verify.get("mpv_path") == WRAPPER,
        "production_seed_has_no_totem_identity_or_token": (
            all(not seed_verify.get(key) for key in production_seed_sensitive_fields(seed_verify))
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_lab_firstboot_artifacts_absent": (
            all(not present(path) for path in PRODUCTION_FORBIDDEN_LAB_PATHS)
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_lab_state_dir_absent": (
            not present("/data/state/totem-read-only-image-lab")
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_overlayroot_disabled": (
            present(PRODUCTION_ARMBIAN_ENV)
            and "rootdev=" in production_armbian_env_now
            and "rootfstype=ext4" in production_armbian_env_now
            and "overlayroot=" not in production_armbian_env_now
            and all(not present(path) for path in PRODUCTION_OVERLAYROOT_PATHS)
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_armbian_host_key_regeneration_disabled": (
            present(PRODUCTION_ARMBIAN_FIRSTRUN_CONFIG)
            and production_armbian_firstrun_config_now.splitlines().count(
                "OPENSSHD_REGENERATE_HOST_KEYS=false"
            ) == 1
            and production_armbian_firstrun_config_now.splitlines().count(
                "OPENSSHD_REGENERATE_HOST_KEYS=true"
            ) == 0
            and present(PRODUCTION_ARMBIAN_FIRSTRUN_SCRIPT)
            and "if [[ \"${OPENSSHD_REGENERATE_HOST_KEYS}\" = true ]]"
            in production_armbian_firstrun_script_now
            and "rm -f /etc/ssh/ssh_host*" in production_armbian_firstrun_script_now
            and present(PRODUCTION_ARMBIAN_FIRSTRUN_UNIT)
            and systemd_unit_directive_has_token(
                production_armbian_firstrun_unit_now,
                "After",
                "ssh.service",
            )
            and systemd_unit_has_exact_directive(
                production_armbian_firstrun_unit_now,
                "EnvironmentFile",
                "/etc/default/armbian-firstrun",
            )
            and systemd_unit_has_exact_directive(
                production_armbian_firstrun_unit_now,
                "ExecStart",
                "/usr/lib/armbian/armbian-firstrun start",
            )
            and production_armbian_firstrun_wants_stat.get("type") == "symlink"
            and production_armbian_firstrun_wants_target
            == PRODUCTION_ARMBIAN_FIRSTRUN_UNIT
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_rootfs_auto_expand_enabled": (
            present(PRODUCTION_ROOTFS_RESIZE_SCRIPT)
            and execu(PRODUCTION_ROOTFS_RESIZE_SCRIPT)
            and present(PRODUCTION_ROOTFS_RESIZE_UNIT)
            and systemd_unit_has_exact_directive(
                production_rootfs_resize_unit_now,
                "ExecStart",
                "/usr/lib/armbian/armbian-resize-filesystem start",
            )
            and production_rootfs_resize_wants_stat.get("type") == "symlink"
            and production_rootfs_resize_wants_target == PRODUCTION_ROOTFS_RESIZE_UNIT
            and not present(PRODUCTION_ROOTFS_RESIZE_DISABLE_MARKER)
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_free_space_zeroed": verify_free_space_zeroed,
        "production_kiosky_commit_marker_matches_c25b": (
            kiosky_commit_marker_now == PLAYER_RUNTIME_BASELINE_SOURCE_COMMIT
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_playback_summary_marker_matches": (
            f"playback_health_summary_commit={PRODUCTION_IMAGE_BOUND_PLAYBACK_SUMMARY_COMMIT}"
            in marker_now
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_ssh_host_keys_not_embedded": (
            all(not present(path) for path in PRODUCTION_EMBEDDED_SSH_HOST_KEYS)
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_machine_id_is_empty": (
            present("/etc/machine-id") and len(machine_id_verify) == 0
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_root_password_hash_replaced": (
            production_old_root_password_hashes_absent is True
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_root_password_matches_external_credential": (
            set(production_root_password_hashes_now) == set(PRODUCTION_SHADOW_PATHS)
            and all(
                hmac.compare_digest(password_hash, production_root_password_hash)
                for password_hash in production_root_password_hashes_now.values()
            )
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_root_password_plaintext_absent": production_root_password_plaintext_absent,
        "production_old_root_password_hashes_absent": production_old_root_password_hashes_absent,
        "production_known_private_residues_absent": production_known_private_residues_absent,
        "production_credential_csprng_provenance_valid": (
            production_credential_provenance.get("schema") == PRODUCTION_CREDENTIAL_PROVENANCE_SCHEMA
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_shadow_permissions_preserved": (
            set(production_shadow_stats_now) == set(PRODUCTION_SHADOW_PATHS)
            and all(
                production_shadow_stats_now[path].get("present") is True
                and production_shadow_stats_now[path].get("uid") == 0
                and production_shadow_stats_now[path].get("gid") == production_shadow_entries[path]["gid"]
                and (int(production_shadow_stats_now[path].get("mode", 0)) & 0o777)
                == production_shadow_entries[path]["mode"]
                for path in PRODUCTION_SHADOW_PATHS
            )
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_identity_init_script_present": (
            present(PRODUCTION_IDENTITY_SCRIPT)
            and execu(PRODUCTION_IDENTITY_SCRIPT)
            and production_identity_init_contract_valid(production_identity_script_now)
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_identity_init_unit_enabled": (
            present(PRODUCTION_IDENTITY_UNIT)
            and present(PRODUCTION_IDENTITY_WANTS)
            and "Before=ssh.service sshd.service" in production_identity_unit_now
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_ssh_requires_identity_init": (
            present(PRODUCTION_SSH_DROPIN)
            and "Requires=totem-production-identity-init.service" in production_ssh_dropin_now
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_settings_policy_embedded_by_totem_core": (
            present(PRODUCTION_SETTINGS_POLICY)
            and execu(PRODUCTION_SETTINGS_POLICY)
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_open_settings_uses_production_policy": (
            present(PRODUCTION_OPEN_SETTINGS_UNIT)
            and "totem_settings_production_apply_policy.py --write" in production_open_settings_unit_now
            and "TOTEM_VISUAL_WIZARD_PAIRING_MODE=production" in production_open_settings_unit_now
            and "TOTEM_VISUAL_WIZARD_PAIRING_API_BASE_URL=https://" in production_open_settings_unit_now
            and "totem_settings_lab_apply_policy" not in production_open_settings_unit_now
            and "homologation" not in production_open_settings_unit_now.lower()
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_lab_settings_policy_absent": (
            not present(PRODUCTION_LAB_SETTINGS_POLICY)
            if args.image_profile == "production"
            else "n/a"
        ),
        "player_runtime_production_authorization_gate_passed": (
            production_player_runtime_authorization.get("passed") is True
            if args.image_profile == "production"
            else "n/a"
        ),
        "no_real_config_embedded": not present("/data/config/config.json"),
        "no_player_runtime_current_embedded": not present("/data/player-runtime/current"),
        "no_legacy_kiosky_player_current_embedded": not present("/data/apps/kiosky-player/current"),
        "no_player_runtime_marker_preforged": not present("/data/player-runtime/current/.release_verified.json"),
        "kiosky_service_present": present("/etc/systemd/system/kiosky-player.service"),
        "fsck_clean": fsck_clean,
    }
    offline_ok = all(x is True or x == "n/a" for x in v.values())
    artifact_promoted = False
    if offline_ok:
        os.chmod(build_image, 0o640 if args.image_profile == "production" else 0o660)
        build_sha.write_text(f"{sha}  {OUT_IMAGE.name}\n", encoding="utf-8")
        os.chmod(build_sha, 0o644)
    else:
        L("offline validation failed; final image/sha256 not promoted")

    image_bytes = build_image.stat().st_size
    manifest = {
        "round": round_name, "image_tag": TAG, "image_version": VERSION,
        "image_profile": args.image_profile,
        "totem_core_embed_profile": totem_core_profile,
        **repo,
        "image_file": str(OUT_IMAGE), "image_sha256": sha,
        "image_bytes": image_bytes,
        "artifact_promoted": artifact_promoted,
        "artifact_ready_required": args.image_profile == "production",
        "artifact_ready_file": str(OUT_READY) if args.image_profile == "production" else "n/a",
        "artifact_private": args.image_profile != "production",
        "final_image": args.image_profile == "production",
        "production_predecessor_tag": (
            PRODUCTION_PREDECESSOR_TAG if args.image_profile == "production" else "n/a"
        ),
        "production_predecessor_sha256": (
            PRODUCTION_PREDECESSOR_SHA256 if args.image_profile == "production" else "n/a"
        ),
        "production_successor_scope": (
            list(PRODUCTION_SUCCESSOR_SCOPE) if args.image_profile == "production" else "n/a"
        ),
        "production_image_bound_transaction_commit": (
            PRODUCTION_IMAGE_BOUND_TRANSACTION_COMMIT
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_image_bound_playback_summary": (
            production_playback_summary_provenance
            if args.image_profile == "production"
            else "n/a"
        ),
        "base_image_line": "c17.4.2", "c17_7_used_as_base": False,
        "base_image": BASE_IMAGE.name,
        "kernel_touched": False, "kernel_rebuild_executed": False,
        "u_boot_touched": False, "dtb_touched": False,
        "c12_readonly_touched": args.image_profile == "production",
        "c12_readonly_blocked": args.image_profile == "production",
        "production_rootfs_mode": "ext4_rw" if args.image_profile == "production" else "n/a",
        "production_overlayroot_disabled": v["production_overlayroot_disabled"],
        "production_armbian_host_key_regeneration_disabled": v[
            "production_armbian_host_key_regeneration_disabled"
        ],
        "production_rootfs_auto_expand_enabled": v["production_rootfs_auto_expand_enabled"],
        "production_free_space_zeroed": v["production_free_space_zeroed"],
        "production_zerofree_summary": verify_zerofree_summary,
        "production_zerofree_tool_sha256": zerofree_tool_sha256,
        "production_ext4_tools": production_ext4_tools,
        "production_root_password_tool": production_root_password_tool,
        "production_credential_provenance": production_credential_provenance,
        "production_root_password_plaintext_absent": v["production_root_password_plaintext_absent"],
        "production_old_root_password_hashes_absent": v["production_old_root_password_hashes_absent"],
        "production_known_private_residues_absent": v["production_known_private_residues_absent"],
        "external_forensic_audit_required": args.image_profile == "production",
        "artifact_file_mode": oct(build_image.stat().st_mode & 0o777) if offline_ok else "not_promoted",
        "build_host": "x86_64 dev sandbox (rootless debugfs derive; no Armbian/kernel rebuild)",
        "sysroot_source": "Debian Bookworm arm64 .debs (glibc 2.36) — prior C18.RUNTIME PoC",
        "hwdecode_stack_built": True, "stack_reused_from": "C18.RUNTIME B1..B9 (hardware-proven)",
        "ffmpeg_v4l2request_built": True, "mpv_v4l2request_built": True,
        "mpv_patch_applied": True, "libplacebo_egl_gbm_built": True,
        "custom_mpv_installed": True, "custom_ffmpeg_installed": ffmpeg_included,
        "toolchain_note": "GCC-13 cross + static-libstdc++ + __isoc23 shim (libplacebo only); "
                          "libass without harfbuzz. Hardware-proven (B9). "
                          "Recommend GCC-12-clean rebuild for the production image.",
        "player_uses_custom_mpv": True, "player_hwdec_flag": "v4l2request-copy",
        "player_runtime_kiosk_source": str(PLAYER_RUNTIME_KIOSK.relative_to(REPO_ROOT)),
        "player_runtime_kiosk_sha256": kiosk_snapshot_sha,
        "player_runtime_baseline_package": player_runtime_baseline,
        "binary_build_inputs": binary_build_inputs,
        "player_runtime_snapshot_governed": True,
        "player_runtime_verified_marker_required": v["totem_kiosky_launcher_requires_verified_marker"],
        "player_runtime_reconcile_available": v["player_runtime_updatectl_reconcile_available"],
        "player_runtime_lab_thaw_guard": v["player_runtime_lab_thaw_guard_present"],
        "player_runtime_ota_still_frozen": v["player_runtime_ota_still_frozen"],
        "player_runtime_boot_state_evidence_gate": True,
        "player_runtime_fault_injection_gate": True,
        "player_runtime_reconcile_corrupt_state_fail_closed": True,
        "player_runtime_gate_semantic_mpv_args": v["player_runtime_release_gate_passed"],
        "player_runtime_release_gate_passed": v["player_runtime_release_gate_passed"],
        "player_runtime_sandbox_passed": v["player_runtime_sandbox_passed"],
        "player_vo": "gpu", "player_gpu_context": "drm", "player_rotation": "from config/wizard (0 in current C18 baseline)",
        "mpv_ipc_preserved": True,
        "totem_in_video_group": v["totem_in_video_group"],
        "r4_updater_perms_preserved": v["r4_updater_perms_present"],
        "totem_core_ota_ready": v["totem_core_ota_ready"],
        "totem_core_embed": totem_core_embed,
        "player_runtime_production_authorization_gate": production_player_runtime_authorization,
        "totem_core_offline_validation": totem_core_validation,
        "offline_validation_passed": offline_ok,
        "offline_validation_detail": v,
        "stack_lib_count": len(real_files), "stack_symlink_count": len(symlinks),
        "sources": SOURCES,
        "supersedes": "c18-hwdecode-lab-1 (kiosk.py banner SyntaxError) & 1b (--no-osc fatal on no-Lua mpv) & 1c (zero-copy panfrost js faults on portrait media) & 1d (playback stable, totem-core OTA layout missing from image) & 1g (player launcher still inside totem-core boundary) & 1h (homologation seed reset mpv_path to stock mpv) & 1i (player-runtime path still split from launcher default) & 1j (golden delivery, before player-runtime thaw foundation) & 1k (validated golden before pre-thaw hardening gap closure) & 1l (golden delivery, before post-audit deep-health/freeze/docs lock) & 1n (golden delivery before guarded reconcile/evidence-gate hardening) & 1o (golden delivery before audit-ready persistent /data trial tooling) & 1p (boot reconcile ran as totem, so /data/player-runtime hygiene was non-effective) & 1q (golden delivery before multi-segment deep-health gate and persistent-trial abort cleanup) & 1r (golden delivery before cold-boot/power-loss pre-hardening gates) & 1s (golden delivery before boot-state evidence and crash-boundary gates) & 1t (golden delivery before post-M6 reconcile freeze hardware proof) & 1u (golden delivery before physical power-loss/soak/server-side gates)",
        "fix_kiosk_read": "read via debugfs dump (cat appended the stderr banner -> SyntaxError); + py_compile added to validation",
        "fix_wrapper_no_osc": "wrapper strips --no-osc (no-Lua mpv has no OSC option -> would fatal-exit before IPC)",
        "fix_wrapper_hwdec_copy": "wrapper forces v4l2request-copy to avoid the runtime panfrost js faults observed on the zero-copy drm_prime path for some portrait media",
        "fix_c17_4_trace_dir": "kiosky-player drop-in moves optional C17.4 firstboot trace from /data to /run so mmc I/O stalls cannot block startup before kiosk.py",
        "fix_player_runtime_path": "totem-kiosky-launcher default now uses /data/player-runtime/current; legacy /data/apps/kiosky-player/current no longer shadows the image player on C18",
        "fix_player_runtime_thaw_foundation": "player-runtime remains frozen (rc=44) but image includes marker-bound launcher adoption, updatectl reconcile/state hygiene, lab thaw guard, quarantine and verify-then-promote primitives for future homologation",
        "fix_player_runtime_boot_evidence": "cold-boot evidence requires boot-id/btime discriminators and /data adoption proof before any /data trial claim",
        "fix_player_runtime_crash_boundary": "player-runtime apply/rollback fault-injection hooks prove fail-closed outcomes before physical power-loss testing",
        "panfrost_rebind_service": True,
        "kiosk_py_compiles": v["kiosk_py_compiles"],
        "hw_validated_live": "C18.IMAGE-LAB.2 on board 2026-06-01: hwdec-current=v4l2request, media_load_failed=0, playing H.264, mpv stable, CPU low",
        "ready_for_manual_card_flash": offline_ok and args.image_profile != "production",
        "ready_for_c18_image_lab_2_clean_board_validation": offline_ok,
        "ready_for_c18_production_candidate_validation": offline_ok if args.image_profile == "production" else False,
        "hardware_validation_required": True,
        "card_written": False, "board_touched": False, "ssh_used": False,
    }
    if args.image_profile == "lab":
        manifest["not_for_production"] = True
        manifest["not_for_distribution"] = True
    else:
        manifest["production_image"] = True
        manifest["supersedes_production_image"] = (
            f"{PRODUCTION_PREDECESSOR_TAG} (board-validated predecessor; candidate adds "
            "C26 local recovery while preserving the image-bound playback baseline)"
        )
        manifest["production_access_nonclaim"] = (
            "CSPRNG-generated shared support password SSH access remains enabled by explicit "
            "first-scale risk acceptance; per-device credentials remain roadmap"
        )
    if args.image_profile == "production":
        if validate_binary_build_inputs() != binary_build_inputs:
            raise SystemExit("BLOCKED: binary image inputs changed during construction")
        if validate_player_runtime_baseline_package() != player_runtime_baseline:
            raise SystemExit("BLOCKED: player-runtime baseline changed during construction")
        repo_after_build = repo_identity()
        if repo_after_build != repo or repo_after_build["repo_dirty"]:
            raise SystemExit("BLOCKED: production source tree changed during image construction")
        out_dir.mkdir(parents=True, exist_ok=False)
        atomic_write(
            out_dir / "build_manifest.json",
            (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
        )
        atomic_write(
            out_dir / "offline_validation.json",
            (json.dumps(v, indent=2) + "\n").encode("utf-8"),
        )
        atomic_write(out_dir / "build.log", ("\n".join(log) + "\n").encode("utf-8"))
        if offline_ok:
            publish_file_exclusive(build_image, OUT_IMAGE)
            promotion_state["image_created"] = True
            publish_file_exclusive(build_sha, OUT_SHA)
            promotion_state["sha_created"] = True
            artifact_promoted = True
            manifest["artifact_promoted"] = True
            manifest["artifact_file_mode"] = oct(OUT_IMAGE.stat().st_mode & 0o777)
            L(f"promoted_image={OUT_IMAGE.name}")
            L(f"promoted_sha256={OUT_SHA.name}")
            atomic_write(
                out_dir / "build_manifest.json",
                (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
            )
            atomic_write(out_dir / "build.log", ("\n".join(log) + "\n").encode("utf-8"))
            ready = {
                "schema": "dadooh.c18.production_image_artifact_ready.v1",
                "image_tag": TAG,
                "image_version": VERSION,
                "image_file": str(OUT_IMAGE),
                "image_sha256": sha,
                "sha256_file": str(OUT_SHA),
                "repo_commit": repo["repo_commit"],
                "repo_tree": repo["repo_tree"],
                "build_manifest_sha256": base.file_sha256(out_dir / "build_manifest.json"),
                "offline_validation_sha256": base.file_sha256(out_dir / "offline_validation.json"),
                "build_log_sha256": base.file_sha256(out_dir / "build.log"),
                "evidence_directory": str(out_dir),
                "external_forensic_audit_required": True,
                "ready_for_manual_card_flash": False,
            }
            publish_bytes_exclusive(
                OUT_READY,
                (json.dumps(ready, indent=2) + "\n").encode("utf-8"),
            )
            promotion_state["ready_created"] = True
        promotion_state["evidence_complete"] = True
    else:
        if offline_ok:
            os.replace(build_image, OUT_IMAGE)
            promotion_state["image_created"] = True
            os.replace(build_sha, OUT_SHA)
            promotion_state["sha_created"] = True
            artifact_promoted = True
            manifest["artifact_promoted"] = True
            manifest["artifact_file_mode"] = oct(OUT_IMAGE.stat().st_mode & 0o777)
            L(f"promoted_image={OUT_IMAGE.name}")
            L(f"promoted_sha256={OUT_SHA.name}")
        out_dir.mkdir(parents=True, exist_ok=True)
        for target in {work, out_dir}:
            atomic_write(
                target / "build_manifest.json",
                (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
            )
            atomic_write(
                target / "offline_validation.json",
                (json.dumps(v, indent=2) + "\n").encode("utf-8"),
            )
            atomic_write(target / "build.log", ("\n".join(log) + "\n").encode("utf-8"))
        promotion_state["evidence_complete"] = True
    print(f"\n=== {round_name} RESULT ===")
    print(json.dumps(manifest, indent=2))
    print(f"\nWORKDIR={'ephemeral_removed_on_exit' if args.image_profile == 'production' else work}")
    print(f"OFFLINE_VALIDATION_PASSED={offline_ok}")
    return 0 if offline_ok else 3


if __name__ == "__main__":
    sys.exit(main())
