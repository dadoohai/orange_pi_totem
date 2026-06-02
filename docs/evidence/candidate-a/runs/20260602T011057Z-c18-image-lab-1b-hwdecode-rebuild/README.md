# C18.IMAGE-LAB.1b — corrected HW-decode image-lab rebuild

Corrects the defective **C18.IMAGE-LAB.1** image after its first hardware boot
(start of C18.IMAGE-LAB.2 clean-board validation) exposed two issues. Offline,
rootless (debugfs) re-derive from the validated **C17.4.2** image. No Armbian/kernel
rebuild, no card write (here), no board change persisted, no C12/read-only change,
no secrets.

## Why a rebuild (the two issues found on hardware — see memory `c18-image-lab-2-firstboot-obs`)
1. **Player stuck on "iniciando player"** = `kiosk.py` `SyntaxError` at line 3425. The
   injected file's last line was literally `debugfs 1.47.0 (5-Feb-2023)` — the **debugfs
   version banner**. ROOT CAUSE (my deriver bug): kiosk.py was read with the
   `cat_file`/`debugfs` helper that concatenates **stdout+stderr**, and debugfs emits its
   banner on stderr → it got appended to the file, then written back → launcher crash-loops.
2. **GPU absent at boot:** `panfrost 1800000.gpu: probe ... error -110 (deferred probe
   timeout)`, no `/dev/dri/renderD128`. The GPU is **healthy** — a surgical re-bind
   (`echo 1800000.gpu > /sys/bus/platform/drivers/panfrost/bind`) brought it up immediately
   (`mali-g31`, `Initialized panfrost 1.2.0`, `renderD128` appeared). It's a **boot-timing
   deferred-probe race**. Without the GPU, `--vo=gpu` would fail even after #1.

## Fixes in 1b
- **kiosk.py read via `debugfs dump`** (binary-faithful; banner stays on stderr) instead of
  `cat`; AND a **`python3 py_compile`** check added to the offline validation (the gap that
  let v1 ship — validation only checked the mpv_path string, never compiled the file).
- **`totem-panfrost-rebind` oneshot systemd service** (userspace; NO kernel/DTB/cmdline)
  ordered **before kiosky-player**, `ConditionPathExists=!/dev/dri/renderD128`, that binds
  panfrost if the render node is missing. Makes the GPU deterministic at boot.

## Image
```
image=Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1b_minimal.img
sha256=27ed29064a087091bdfc448560c93f217d032d9104a753b04c5ae7f65e701bf3
bytes=1971322880   supersedes=c18-hwdecode-lab-1 (defective; kept as evidence)
artifact_private=true final_image=false not_for_production=true not_for_distribution=true
base_image_line=c17.4.2  c17_7_used_as_base=false
kernel_touched=false u_boot_touched=false dtb_touched=false c12_readonly_touched=false
ready_for_manual_card_flash=true  ready_for_c18_image_lab_2_clean_board_validation=true
```

## Offline validation — all passed (incl. the new checks)
`offline_validation.json`: `kiosk_py_compiles=true`, `panfrost_rebind_script/unit/enabled/
before_player=true`, `player_points_to_wrapper=true`, `player_no_longer_default_mpv=true`,
custom mpv+ffmpeg+11 libs/21 symlinks present, wrapper forces vo=gpu/gpu-context=drm/
hwdec=v4l2request, R4 present, totem in video group, marker final_image=false, no real
config, fsck clean. (ELF/dependency closure was proven for the identical stack in the v1
recovery: `elf_missing_libs=[]`.)

## Next — C18.IMAGE-LAB.2 (clean-board validation, hardware)
Re-flash **1b** (Armbian Imager; verify sha `27ed2906...`) → clean boot → expect: no
crash-loop (player reaches "tocando"), panfrost up at boot (renderD128 present),
`Using hardware decoding (v4l2request)`, zero-copy on HDMI + 270° rotation, no terminal
flash, `media_load_failed`≈0. The board is at 192.168.18.131 (SSH) for validation.

## Guardrails
```
image_flashed_here=false card_written=false board_persistent_change=false
kernel/u-boot/dtb/c12_readonly_touched=false apt_upgrade=false real_config/secrets_embedded=false
limitation_C_accepted=false  panfrost_rebind=userspace_only(no_kernel_cmdline)
```
