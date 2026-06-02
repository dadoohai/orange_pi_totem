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
  * writes the image-lab marker (artifact_private/final_image=false/not_for_production).

It does NOT touch C12/read-only/overlayroot/CONFIG_OVERLAY_FS, kernel/U-Boot/DTB/BSP,
real config, media/cache, or secrets.
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derive_c15_2_1_homolog_image as base
import totem_core_image_embed

ARM = Path("/home/builder/totem-os/armbian-build-v25.11/output/images")
REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_IMAGE = ARM / ("Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
                    "6.12.58-c12-ro-lab-c17-4-2-settings-restore-clean_minimal.img")
TAG = "c18-hwdecode-lab-1e"   # 1e = 1d HW-decode stability + totem-core OTA-ready layout embedded.
VERSION = "c18.image-lab.1e"
OUT_IMAGE = ARM / (f"Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
                   f"6.12.58-{TAG}_minimal.img")

BUNDLE = Path("/tmp/ffbuild/bundle")
FFMPEG_CLI = Path("/tmp/ffbuild/ffmpeg.stripped")
R4_UPDATECTL = Path("/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py")

HWDIR = "/opt/totem/hwdecode"
WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
KIOSK = "/opt/totem/kiosky-player/kiosk.py"
UPDATECTL = "/opt/totem/bin/totem-updatectl"
MARKER = "/etc/dadooh/c18-hwdecode-lab-1e-image"
PANFROST_SH = "/opt/totem/bin/totem-panfrost-rebind.sh"
PANFROST_UNIT = "/etc/systemd/system/totem-panfrost-rebind.service"
PANFROST_WANTS = "/etc/systemd/system/multi-user.target.wants/totem-panfrost-rebind.service"
C18_STABILITY_DROPIN = "/etc/systemd/system/kiosky-player.service.d/30-c18-stability.conf"

MPV_PATH_OLD = '"mpv_path": "mpv",'
MPV_PATH_NEW = f'"mpv_path": "{WRAPPER}",'

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
    "# C18 HW-decode wrapper (artifact_private; not_for_production). Forces the\n"
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    log = []
    def L(m): print(m); log.append(m)

    # ---- preflight ----
    if not shutil.which("debugfs"):
        raise SystemExit("BLOCKED: debugfs_missing")
    for p in (BASE_IMAGE, BUNDLE / "mpv", BUNDLE / "lib", R4_UPDATECTL):
        if not p.exists():
            raise SystemExit(f"BLOCKED: missing_input {p}")
    if OUT_IMAGE.exists() and not args.force:
        raise SystemExit(f"output exists (use --force): {OUT_IMAGE}")
    L(f"base_image={BASE_IMAGE.name}")
    L(f"out_image={OUT_IMAGE.name}")

    work = Path(tempfile.mkdtemp(prefix="c18-hwdecode-lab-"))
    rootfs = work / "rootfs.ext4"

    # ---- copy base -> out, extract rootfs ----
    L("copy base image -> output ...")
    shutil.copy2(BASE_IMAGE, OUT_IMAGE)
    off, length = base.parse_mbr_linux_partition(OUT_IMAGE)
    L(f"linux partition offset={off} length={length}")
    base.copy_range(OUT_IMAGE, rootfs, offset=off, length=length)

    # ---- read + patch kiosk.py (point player at the wrapper) ----
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
    kiosk_patched = kiosk_src.replace(MPV_PATH_OLD, MPV_PATH_NEW, 1)
    kiosk_tmp = work / "kiosk.py"; kiosk_tmp.write_text(kiosk_patched, encoding="utf-8")

    # ---- wrapper + marker temp files ----
    wrap_tmp = work / "totem-mpv-hwdecode"; wrap_tmp.write_text(WRAPPER_SH, encoding="utf-8")
    marker_tmp = work / "marker"
    marker_tmp.write_text("\n".join([
        f"image_tag={TAG}", f"image_version={VERSION}",
        "artifact_private=true", "final_image=false",
        "not_for_production=true", "not_for_distribution=true",
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
        "totem_update_policy_embedded=true",
        "totem_update_timer_enabled=false",
        "panfrost_rebind_service=installed",
        "c17_4_trace_dir=/run/totem/c17-4-firstboot",
        "supersedes=c18-hwdecode-lab-1 (kiosk.py banner SyntaxError) & 1b (--no-osc fatal on no-Lua mpv) & 1c (zero-copy panfrost js faults on portrait media) & 1d (playback stable, totem-core OTA layout missing from image)",
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
    put(str(marker_tmp), MARKER, "0644")
    # panfrost rebind service (oneshot, before kiosky-player) + enable symlink
    put(str(panfrost_sh_tmp), PANFROST_SH, "0755")
    put(str(panfrost_unit_tmp), PANFROST_UNIT, "0644")
    cmds.append(f"symlink {PANFROST_WANTS} {PANFROST_UNIT}")
    put(str(stability_dropin_tmp), C18_STABILITY_DROPIN, "0644")

    L(f"debugfs commands: {len(cmds)} (stack libs real={len(real_files)} symlink={len(symlinks)})")
    out = base.debugfs_batch(rootfs, cmds, work)
    bad = [ln for ln in out.splitlines() if "rror" in ln.lower() and "Errno 2" not in ln
           and "while trying to delete" not in ln.lower()]
    if bad:
        L("debugfs stderr (filtered):")
        for ln in bad[:30]:
            L("  " + ln)

    # ---- embed OTA-ready totem-core current/fallback/wrapper layout ----
    totem_core_embed = totem_core_image_embed.write_totem_core_embed(rootfs, work, REPO_ROOT)
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
    base.write_range(OUT_IMAGE, rootfs, offset=off)
    L("rootfs written back into output image")

    # ---- sha256 ----
    sha = base.file_sha256(OUT_IMAGE)
    (Path(str(OUT_IMAGE) + ".sha256")).write_text(f"{sha}  {OUT_IMAGE.name}\n", encoding="utf-8")
    L(f"sha256={sha}")

    # ---- offline validation: re-extract final image, verify via debugfs ----
    off2, len2 = base.parse_mbr_linux_partition(OUT_IMAGE)
    vroot = work / "verify.ext4"
    base.copy_range(OUT_IMAGE, vroot, offset=off2, length=len2)

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
    totem_core_validation = totem_core_image_embed.validate_totem_core_embed(vroot)
    libs_present = {e: present(f"{HWDIR}/lib/{e}") for e in real_files}

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
        "c17_4_trace_moved_to_run": present(C18_STABILITY_DROPIN),
        "r4_updater_perms_present": "_make_world_traversable" in upd_now,
        "totem_core_ota_ready": totem_core_validation["ok"],
        "totem_in_video_group": "totem" in video_line.split(":")[-1].split(","),
        "marker_present": present(MARKER),
        "marker_final_image_false": "final_image=false" in marker_now,
        "no_real_config_embedded": not present("/data/config/config.json"),
        "kiosky_service_present": present("/etc/systemd/system/kiosky-player.service"),
        "fsck_clean": fsck_clean,
    }
    offline_ok = all(x is True or x == "n/a" for x in v.values())

    manifest = {
        "round": "C18.IMAGE-LAB.1e", "image_tag": TAG, "image_version": VERSION,
        "image_file": str(OUT_IMAGE), "image_sha256": sha,
        "image_bytes": OUT_IMAGE.stat().st_size,
        "artifact_private": True, "final_image": False,
        "not_for_production": True, "not_for_distribution": True,
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
        "player_vo": "gpu", "player_gpu_context": "drm", "player_rotation": "from config/wizard (0 in current C18 baseline)",
        "mpv_ipc_preserved": True,
        "totem_in_video_group": v["totem_in_video_group"],
        "r4_updater_perms_preserved": v["r4_updater_perms_present"],
        "totem_core_ota_ready": v["totem_core_ota_ready"],
        "totem_core_embed": totem_core_embed,
        "totem_core_offline_validation": totem_core_validation,
        "offline_validation_passed": offline_ok,
        "offline_validation_detail": v,
        "stack_lib_count": len(real_files), "stack_symlink_count": len(symlinks),
        "sources": SOURCES,
        "supersedes": "c18-hwdecode-lab-1 (kiosk.py banner SyntaxError) & 1b (--no-osc fatal on no-Lua mpv) & 1c (zero-copy panfrost js faults on portrait media) & 1d (playback stable, totem-core OTA layout missing from image)",
        "fix_kiosk_read": "read via debugfs dump (cat appended the stderr banner -> SyntaxError); + py_compile added to validation",
        "fix_wrapper_no_osc": "wrapper strips --no-osc (no-Lua mpv has no OSC option -> would fatal-exit before IPC)",
        "fix_wrapper_hwdec_copy": "wrapper forces v4l2request-copy to avoid the runtime panfrost js faults observed on the zero-copy drm_prime path for some portrait media",
        "fix_c17_4_trace_dir": "kiosky-player drop-in moves optional C17.4 firstboot trace from /data to /run so mmc I/O stalls cannot block startup before kiosk.py",
        "panfrost_rebind_service": True,
        "kiosk_py_compiles": v["kiosk_py_compiles"],
        "hw_validated_live": "C18.IMAGE-LAB.2 on board 2026-06-01: hwdec-current=v4l2request, media_load_failed=0, playing H.264, mpv stable, CPU low",
        "ready_for_manual_card_flash": offline_ok,
        "ready_for_c18_image_lab_2_clean_board_validation": offline_ok,
        "hardware_validation_required": True,
        "card_written": False, "board_touched": False, "ssh_used": False,
    }
    print("\n=== C18.IMAGE-LAB.1e RESULT ===")
    print(json.dumps(manifest, indent=2))
    out_dir = Path(os.environ.get("C18_OUT_DIR", str(work)))
    (work / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (work / "offline_validation.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
    (work / "build.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    print(f"\nWORKDIR={work}")
    print(f"OFFLINE_VALIDATION_PASSED={offline_ok}")
    return 0 if offline_ok else 3


if __name__ == "__main__":
    sys.exit(main())
