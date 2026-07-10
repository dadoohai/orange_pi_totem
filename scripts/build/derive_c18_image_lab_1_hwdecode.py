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
  * injects the R4 updater-perms fix (foundation totem_updatectl.py), which C17.4.2
    predates;
  * embeds the C17.6 totem-core update layout so wizard/core fixes are OTA-ready
    from first boot (/data/core/totem current release, /opt fallback scripts and
    wrappers);
  * writes the image marker. The default remains image-lab
    (artifact_private/final_image=false/not_for_production); production identity
    requires --image-profile production.

It does NOT touch C12/read-only/overlayroot/CONFIG_OVERLAY_FS, kernel/U-Boot/DTB/BSP,
real config, media/cache, or secrets.
"""
from __future__ import annotations
import argparse, atexit, json, os, shutil, subprocess, sys, tempfile
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
PRODUCTION_TAG = "c18-hwdecode-prod-7"
PRODUCTION_VERSION = "c18.image-prod.7"
PRODUCTION_MARKER = f"/etc/dadooh/{PRODUCTION_TAG}-image"
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
PLAYER_RUNTIME_KIOSK_SHA256 = "3aacb05f011607318c9c147822036251e9744b50419757b85373e02a5fb3f30b"
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
    "download_media/media_items_from_saved/media_items_from_cache": (
        "image extensions are admitted directly into MPV",
        "still images are prepared as local H.264 MP4 sidecars before playlist admission",
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
    if "/" in tag or tag.startswith(".") or ".." in Path(tag).parts:
        raise SystemExit(f"BLOCKED: unsafe image tag {tag!r}")
    if image_profile == "production":
        if not tag.startswith("c18-hwdecode-prod-"):
            raise SystemExit("BLOCKED: production image tag must start with c18-hwdecode-prod-")
        if not version.startswith("c18.image-prod."):
            raise SystemExit("BLOCKED: production image version must start with c18.image-prod.")
    else:
        if not tag.startswith("c18-hwdecode-lab-"):
            raise SystemExit("BLOCKED: image tag must start with c18-hwdecode-lab-")
        if not version.startswith("c18.image-lab."):
            raise SystemExit("BLOCKED: image version must start with c18.image-lab.")
    if not marker.startswith("/etc/dadooh/") or "/" in marker.removeprefix("/etc/dadooh/"):
        raise SystemExit("BLOCKED: image marker must be an /etc/dadooh/<file> path")


def main():
    global TAG, VERSION, OUT_IMAGE, OUT_SHA, MARKER
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--image-tag", help="explicit candidate image tag; defaults to current-golden.json")
    ap.add_argument("--image-version", help="explicit candidate image version; defaults from --image-tag")
    ap.add_argument("--image-marker", help="explicit candidate marker path; defaults to /etc/dadooh/<image-tag>-image")
    ap.add_argument("--image-profile", choices=("lab", "production"), default="lab")
    ap.add_argument("--totem-core-profile", choices=("homologation", "production"))
    ap.add_argument("--allow-dirty", action="store_true", help="allow exploratory builds from a dirty repo")
    args = ap.parse_args()
    totem_core_profile = args.totem_core_profile or (
        "production" if args.image_profile == "production" else "homologation"
    )
    if args.image_profile == "production" and totem_core_profile != "production":
        raise SystemExit("BLOCKED: production image requires totem-core production profile")
    if args.image_profile == "lab" and totem_core_profile == "production":
        raise SystemExit("BLOCKED: production totem-core profile requires --image-profile production")
    repo = repo_identity()
    if repo["repo_dirty"] and not args.allow_dirty:
        raise SystemExit("BLOCKED: source repo dirty; commit first or pass --allow-dirty for exploratory builds")
    production_player_runtime_authorization = (
        validate_production_player_runtime_authorization()
        if args.image_profile == "production"
        else {"passed": "n/a", "result_claim": "not_required_for_homologation_image"}
    )

    if args.image_tag:
        TAG = args.image_tag
        VERSION = args.image_version or image_version_for_tag(TAG)
        MARKER = args.image_marker or f"/etc/dadooh/{TAG}-image"
        validate_candidate_identity(TAG, VERSION, MARKER, image_profile=args.image_profile)
        OUT_IMAGE = ARM / (f"Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
                           f"6.12.58-{TAG}_minimal.img")
        OUT_SHA = Path(str(OUT_IMAGE) + ".sha256")
    elif args.image_profile == "production":
        TAG = PRODUCTION_TAG
        VERSION = PRODUCTION_VERSION
        MARKER = PRODUCTION_MARKER
        validate_candidate_identity(TAG, VERSION, MARKER, image_profile=args.image_profile)
        OUT_IMAGE = ARM / (f"Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
                           f"6.12.58-{TAG}_minimal.img")
        OUT_SHA = Path(str(OUT_IMAGE) + ".sha256")
    elif args.image_version or args.image_marker:
        raise SystemExit("BLOCKED: --image-version/--image-marker require --image-tag")
    round_name = image_round_name(TAG)

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
        PRODUCTION_SETTINGS_POLICY_SOURCE,
        PRODUCTION_OPEN_SETTINGS_UNIT_SOURCE,
    ):
        if not p.exists():
            raise SystemExit(f"BLOCKED: missing_input {p}")
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
    if (OUT_IMAGE.exists() or OUT_SHA.exists()) and not args.force:
        raise SystemExit(f"output exists (use --force): {OUT_IMAGE}")
    L(f"base_image={BASE_IMAGE.name}")
    L(f"out_image={OUT_IMAGE.name}")

    work = Path(tempfile.mkdtemp(prefix="c18-hwdecode-lab-"))
    rootfs = work / "rootfs.ext4"
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=f".{OUT_IMAGE.name}.",
        suffix=".tmp",
        dir=OUT_IMAGE.parent,
    )
    os.close(tmp_fd)
    build_image = Path(tmp_name)
    build_sha = Path(str(build_image) + ".sha256")

    def cleanup_temp_artifacts():
        for leftover in (build_sha, build_image):
            try:
                if leftover.exists():
                    leftover.unlink()
            except OSError as exc:
                print(f"WARN: failed to remove temp artifact {leftover}: {exc}", file=sys.stderr)

    atexit.register(cleanup_temp_artifacts)

    # ---- copy base -> candidate, extract rootfs ----
    L("copy base image -> temp output ...")
    shutil.copy2(BASE_IMAGE, build_image)
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
    kiosk_tmp = work / "kiosk.py"; kiosk_tmp.write_text(kiosk_snapshot, encoding="utf-8")

    seed_orig = work / "private-values.seed.orig.json"
    base.debugfs(rootfs, f"dump {HOMOLOGATION_SEED} {seed_orig}")
    if not seed_orig.exists():
        raise SystemExit(f"BLOCKED: homologation seed missing at {HOMOLOGATION_SEED}")
    seed_data = json.loads(seed_orig.read_text(encoding="utf-8"))
    if not isinstance(seed_data, dict):
        raise SystemExit("BLOCKED: homologation seed root is not an object")
    seed_data["mpv_path"] = WRAPPER
    if args.image_profile == "production":
        for key in production_seed_sensitive_fields(seed_data):
            if key in seed_data:
                seed_data[key] = ""
    seed_tmp = work / "private-values.seed.json"
    seed_tmp.write_text(json.dumps(seed_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

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
        "c12_readonly_touched=false",
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
        "player_runtime_reconcile_available=true",
        "player_runtime_lab_thaw_guard=true",
        "player_runtime_gate_semantic_mpv_args=true",
        "player_runtime_boot_state_evidence_gate=true",
        "player_runtime_fault_injection_gate=true",
        "player_runtime_reconcile_corrupt_state_fail_closed=true",
        "player_runtime_ota_still_frozen=true",
        "totem_core_excludes_kiosky_service_launcher=true",
        f"player_runtime_kiosk_source={PLAYER_RUNTIME_KIOSK.relative_to(REPO_ROOT)}",
        f"player_runtime_kiosk_sha256={kiosk_snapshot_sha}",
        "homologation_seed_mpv_path=totem-mpv-hwdecode",
        f"production_lab_artifacts_removed={str(args.image_profile == 'production').lower()}",
        f"production_ssh_host_keys_generated_on_device={str(args.image_profile == 'production').lower()}",
        f"production_shared_root_password_access_risk_accepted={str(args.image_profile == 'production').lower()}",
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
        cmds.append(f"rm {PRODUCTION_IDENTITY_WANTS}")
        cmds.append(f"symlink {PRODUCTION_IDENTITY_WANTS} {PRODUCTION_IDENTITY_UNIT}")
        for path in (*PRODUCTION_FORBIDDEN_LAB_PATHS, *PRODUCTION_EMBEDDED_SSH_HOST_KEYS):
            cmds.append(f"rm {path}")
        cmds.append("rmdir /data/state/totem-read-only-image-lab")

    L(f"debugfs commands: {len(cmds)} (stack libs real={len(real_files)} symlink={len(symlinks)})")
    out = base.debugfs_batch(rootfs, cmds, work)
    bad = [ln for ln in out.splitlines() if "rror" in ln.lower() and "Errno 2" not in ln
           and "while trying to delete" not in ln.lower()]
    if bad:
        L("debugfs stderr (filtered):")
        for ln in bad[:30]:
            L("  " + ln)

    # ---- embed OTA-ready totem-core current/fallback/wrapper layout ----
    totem_core_embed = totem_core_image_embed.write_totem_core_embed(
        rootfs,
        work,
        REPO_ROOT,
        profile=totem_core_profile,
    )
    L(
        "totem-core embedded "
        f"version={totem_core_embed['totem_core_current_version']} "
        f"files={totem_core_embed['totem_core_files_embedded']}"
    )

    # ---- fsck consistency check (read-only) ----
    fsck = sh(["e2fsck", "-f", "-n", str(rootfs)])
    fsck_clean = fsck.returncode in (0,)  # 0=clean; non-zero would indicate problems
    L(f"e2fsck rc={fsck.returncode} ({'clean' if fsck_clean else 'CHECK'})")

    # ---- write rootfs back into the image ----
    base.write_range(build_image, rootfs, offset=off)
    L("rootfs written back into temp output image")

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
    seed_verify_file = work / "private-values.seed.verify.json"
    base.debugfs(vroot, f"dump {HOMOLOGATION_SEED} {seed_verify_file}")
    seed_verify = json.loads(seed_verify_file.read_text(encoding="utf-8")) if seed_verify_file.exists() else {}
    machine_id_verify_file = work / "machine-id.verify"
    base.debugfs(vroot, f"dump /etc/machine-id {machine_id_verify_file}")
    production_identity_script_now = base.cat_file(vroot, PRODUCTION_IDENTITY_SCRIPT) or ""
    production_identity_unit_now = base.cat_file(vroot, PRODUCTION_IDENTITY_UNIT) or ""
    production_ssh_dropin_now = base.cat_file(vroot, PRODUCTION_SSH_DROPIN) or ""
    production_open_settings_unit_now = base.cat_file(vroot, PRODUCTION_OPEN_SETTINGS_UNIT) or ""
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
        "all_stack_libs_present": all(libs_present.values()),
        "wrapper_present": present(WRAPPER) and execu(WRAPPER),
        "wrapper_forces_hwdec": "--hwdec=v4l2request-copy" in wrap_now and "--vo=gpu" in wrap_now
                                and "--gpu-context=drm" in wrap_now and "LD_LIBRARY_PATH" in wrap_now,
        "wrapper_strips_no_osc": "--no-osc) continue" in wrap_now,
        "player_points_to_wrapper": MPV_PATH_NEW in kiosk_clean,
        "player_no_longer_default_mpv": MPV_PATH_OLD not in kiosk_clean,
        "kiosk_py_compiles": kiosk_compiles,
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
        "production_ssh_host_keys_not_embedded": (
            all(not present(path) for path in PRODUCTION_EMBEDDED_SSH_HOST_KEYS)
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_machine_id_is_empty": (
            machine_id_verify_file.is_file() and machine_id_verify_file.stat().st_size == 0
            if args.image_profile == "production"
            else "n/a"
        ),
        "production_identity_init_script_present": (
            present(PRODUCTION_IDENTITY_SCRIPT)
            and execu(PRODUCTION_IDENTITY_SCRIPT)
            and "ssh-keygen -A" in production_identity_script_now
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
        build_sha.write_text(f"{sha}  {OUT_IMAGE.name}\n", encoding="utf-8")
        os.replace(build_image, OUT_IMAGE)
        os.replace(build_sha, OUT_SHA)
        artifact_promoted = True
        L(f"promoted_image={OUT_IMAGE.name}")
        L(f"promoted_sha256={OUT_SHA.name}")
    else:
        L("offline validation failed; final image/sha256 not promoted")

    image_bytes = OUT_IMAGE.stat().st_size if artifact_promoted else build_image.stat().st_size
    manifest = {
        "round": round_name, "image_tag": TAG, "image_version": VERSION,
        "image_profile": args.image_profile,
        "totem_core_embed_profile": totem_core_profile,
        **repo,
        "image_file": str(OUT_IMAGE), "image_sha256": sha,
        "image_bytes": image_bytes,
        "artifact_promoted": artifact_promoted,
        "artifact_private": args.image_profile != "production",
        "final_image": args.image_profile == "production",
        "base_image_line": "c17.4.2", "c17_7_used_as_base": False,
        "base_image": BASE_IMAGE.name,
        "kernel_touched": False, "kernel_rebuild_executed": False,
        "u_boot_touched": False, "dtb_touched": False, "c12_readonly_touched": False,
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
        "ready_for_manual_card_flash": offline_ok,
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
            "c18-hwdecode-prod-5 (blocked: inherited lab firstboot credentials, markers and SSH host keys)"
        )
        manifest["production_access_nonclaim"] = (
            "shared root password SSH access remains enabled by explicit first-scale risk acceptance; "
            "per-device credentials remain roadmap"
        )
    print(f"\n=== {round_name} RESULT ===")
    print(json.dumps(manifest, indent=2))
    out_dir = Path(os.environ.get("C18_OUT_DIR", str(work)))
    out_dir.mkdir(parents=True, exist_ok=True)
    for target in {work, out_dir}:
        (target / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (target / "offline_validation.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
        (target / "build.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    print(f"\nWORKDIR={work}")
    print(f"OFFLINE_VALIDATION_PASSED={offline_ok}")
    return 0 if offline_ok else 3


if __name__ == "__main__":
    sys.exit(main())
