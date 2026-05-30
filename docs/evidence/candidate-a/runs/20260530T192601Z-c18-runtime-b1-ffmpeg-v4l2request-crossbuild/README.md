# C18.RUNTIME.B1 — Route B: ffmpeg V4L2-Request hwaccel cross-build, validated on board

Decision C18.RUNTIME (team) = **Route B** (patched ffmpeg V4L2-Request + keep mpv).
This round executed the **cross-build feasibility spike** of Route B and validated it
**end-to-end on the production board** — a mature decoder (ffmpeg) hardware-decodes
real High-profile/CABAC/B-frame content via Cedrus at a fraction of the CPU.

NO image built, NO flashing, NO install, NO release, NO client deploy. The
cross-built `ffmpeg` binary was pushed to `/tmp` on the board, run, then removed.
Player service and config untouched; `/dev/video0` left with 0 holders. Sanitized.

## Result (decisive)
Same clip on the same board, 240 frames, 1080p **High profile, CABAC, B-frames**
(generated on-board via libx264; representative of real content), `ffmpeg -benchmark`:

| Path                                   | frames | CPU (utime+stime) | wall (rtime) | cores      |
|----------------------------------------|-------:|------------------:|-------------:|------------|
| Software h264 (today's player path)    |    240 |       **9.98 s**  |    3.06 s    | ~3.2 (saturating) |
| Hardware v4l2request / Cedrus          |    240 |       **0.41 s**  |    1.99 s    | ~0.05      |

- **~24× less CPU** (9.98 s → 0.41 s); from ~3.2 cores down to ~5% of one core.
- HW path confirmed engaged (verbose): `Using V4L2 media driver cedrus (6.12.58)` +
  `Selecting decoder 'h264' because of requested hwaccel method v4l2request`;
  all 240 frames decoded (`frame=240`, incl. B-frames) at up to 121 fps.
- This removes exactly the CPU saturation that stalls `loadfile` and produces the
  false `media_load_failed` (root cause, C18.RUNTIME.3).

## Decision
```
B1_decision = B_BUILD_OK_DECODE_VALIDATED
ffmpeg_source = github.com/Kwiboo/FFmpeg @ v4l2request-2024-v2 (HEAD 2af4006)
hwaccel = v4l2request (h264_v4l2request) ; output = drm_prime (NV12 on VPU, zero CPU copyback)
cross_build = SUCCESS (dynamic-linked vs Bookworm arm64 sysroot; runs on board unmodified)
binary_deps = libm.so.6 libdrm.so.2 libudev.so.1 libc.so.6 ld-linux-aarch64.so.1 (all present on board)
remaining = link mpv 0.35.1 against this ffmpeg (--hwdec=drm) + totem in 'video' group + package TEST image
limitation_C_accepted = false
```

## Remaining work to ship (the gated image round — NOT done here)
1. Build mpv 0.35.1 (or current) linked against this ffmpeg fork; `--hwdec=v4l2request`
   / `--hwdec=drm`, `--vo=gpu`/`drm`. (mpv PR #14511 adds the v4l2request hwdevice.)
2. `totem` user in `video` group (device access; today's test ran as root).
3. Validate on a TEST board: hwdec engages, `media_load_failed`≈0 over ≥25 min,
   CPU/visual ok on HDMI, soak ≥1 h. Pass ⇒ candidate image (separate round).
4. Display interop: drm_prime → panfrost GPU/KMS zero-copy (mpv gpu/drm VO).

See `BUILD.md` for the exact reproducible recipe.

## Guardrails
```
image_built=false kernel_touched=false release_published=false backend_changed=false
real_config_changed=false apt_upgrade/install_on_board=false poweroff=false
c12_readonly_touched=false client_board_deploy=false player_service_touched=false
board_temp_files_removed=true video0_holders_after=0 board_persistent_state_unchanged_by_us=true
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
limitation_C_accepted=false poc_commits_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
```
