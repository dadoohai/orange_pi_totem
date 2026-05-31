# C18.IMAGE-LAB.1 — HW-decode image-lab build (offline) — RECOVERED after WSL I/O failure

Offline, userspace-only, rootless derivation of a private HW-decode **image-lab** from the
hardware-validated **C17.4.2** image. Injects the proven Cedrus/V4L2-Request stack
(C18.RUNTIME B1..B9) + a wrapper that forces the zero-copy display path, points the embedded
player at it, injects R4, and writes the lab marker. **No Armbian/kernel rebuild, no card
write, no board, no SSH, no C12/read-only change, no secrets.**

> Recovery note: WSL hit recurring `EIO` in `/tmp/claude` during the *post-build* ELF check.
> The image was already fully written + SHA256'd before the failure. After restart the image
> SHA re-verified **identical** (full 1.9 GB read, no I/O error) and the offline + ELF
> validation re-ran clean. Status = `recovered_after_wsl_io_failure`. No rebuild was done.

## Status
```
c18_image_lab_1_status=passed_offline_image_build
recovery_status=recovered_after_wsl_io_failure
image_built=true
image_file=/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1_minimal.img
image_sha256=a1103ba822d3bdba1b637a8e602677ee503369d85e8bc8b307d4863bf620e587
image_bytes=1971322880
image_sha256_reverified_after_restart=true

artifact_private=true
final_image=false
not_for_production=true
not_for_distribution=true

base_image_line=c17.4.2
c17_7_used_as_base=false
reason=C17.4.2 is the last hardware-validated image; C17.7 is hardware-unvalidated so it is not a trusted base.
kernel_touched=false
kernel_rebuild_executed=false
u_boot_touched=false
dtb_touched=false
c12_readonly_touched=false

hwdecode_stack_built=true
stack_reused_from=C18.RUNTIME B1..B9 (hardware-proven; survived in /tmp/ffbuild)
ffmpeg_v4l2request_built=true
mpv_v4l2request_built=true
mpv_patch_applied=true
libplacebo_egl_gbm_built=true
custom_mpv_installed=true
custom_ffmpeg_installed=true

player_uses_custom_mpv=true
player_hwdec_flag=v4l2request
player_vo=gpu
player_gpu_context=drm
player_rotation=270   # from config/wizard (homolog default); wrapper preserves --video-rotate
mpv_ipc_preserved=true

totem_in_video_group=true   # already provisioned in C17.4.2 (video:x:44:totem)
r4_updater_perms_preserved=true   # injected (C17.4.2 predated R4)

offline_validation_passed=true
ready_for_manual_card_flash=true
ready_for_c18_image_lab_2_clean_board_validation=true

hardware_validation_required=true
card_written=false
board_touched=false
ssh_used=false
```

## How the player uses HW decode (config-safe, no real config embedded)
- Stack at `/opt/totem/hwdecode/{bin/mpv,bin/ffmpeg,lib/*}` (11 real `.so` + 21 symlinks).
- Wrapper `/opt/totem/bin/totem-mpv-hwdecode`:
  `LD_LIBRARY_PATH=/opt/totem/hwdecode/lib` then
  `exec /opt/totem/hwdecode/bin/mpv "$@" --vo=gpu --gpu-context=drm --hwdec=v4l2request`
  (appended last → overrides whatever the player passed; preserves IPC, `--video-rotate`, etc.).
- `/opt/totem/kiosky-player/kiosk.py` `DEFAULT_CONFIG["mpv_path"]` patched `"mpv"` →
  `"/opt/totem/bin/totem-mpv-hwdecode"`. The board's config does not set `mpv_path`, so the
  wrapper is used; `--video-rotate=270` still flows from config/wizard. IPC/playlist/duration/
  sync/C18.2/F10/NetworkManager untouched.

## ELF / dependency closure (interrupted check, now complete)
`elf_missing_libs = []`. Every NEEDED lib resolves offline: stack libs (libav*, libplacebo,
libass, libfreetype, libfribidi) from `/opt/totem/hwdecode/lib`; system libs
(`libEGL.so.1, libdrm.so.2, libgbm.so.1, libudev.so.1, libm.so.6, libc.so.6,
ld-linux-aarch64.so.1`) all present in the rootfs `/usr/lib/aarch64-linux-gnu/`. libplacebo
is static-libstdc++ (self-contained C++; no libstdc++ runtime dep). See
`offline/recovery-validation.json` and `offline/build_manifest.json`.

## Toolchain note (deviation registered)
Stack reused from C18.RUNTIME (GCC-13 cross + Bookworm-2.36 sysroot; `static-libstdc++` +
`__isoc23` shim in libplacebo only; libass without harfbuzz). **Hardware-proven in B9**
(867 loadfile transitions, 0 failures). The task's preferred GCC-12 clean/no-shim build is
recommended for the *production* image (a Bookworm GCC-12 chroot removes the shim). For this
LAB image, the hardware-proven stack was chosen to minimize untested variables ahead of the
mandatory C18.IMAGE-LAB.2 clean-board hardware validation.

## Guardrails
```
secrets_published=false api_key_published=false api_url_published=false environment_id_published=false
ssid_published=false wifi_password_published=false media_urls_published=false
apt_upgrade_executed=false apt_full_upgrade_executed=false pip_install_executed=false
read_only_touched=false writer_called=false real_config_written=false
poweroff_executed=false power_cut_tested=false c12_4_power_cut_tested=false
c12_readonly_blocked=true c12_4_blocked=true
rebuild_after_io_failure=false card_written=false board_touched=false ssh_used=false
```

## Next
Manual card flash via Armbian Imager (user), then **C18.IMAGE-LAB.2 clean-board validation**:
hwdec engages (`Using hardware decoding (v4l2request)`), zero-copy (no autoconvert download),
on-HDMI visual + 270° rotation, `media_load_failed`≈0 soak, steady 30 fps. See doc 187.
