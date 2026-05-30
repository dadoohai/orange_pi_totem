# C18.RUNTIME.B4 — display zero-copy validation: findings (no flash)

Goal: validate end-to-end HW-decode **+ display** (drm_prime → panfrost, zero-copy) on
the board. Outcome: the decode is proven (B1, 24×) and mpv runs, but the **display path
hit two integration items that are image-round work**, not hardware limits. The board's
live player was stopped/restarted around each display test and is fully restored.

## Board's production player (observed, for reference)
`kiosky-player.service` → `kiosk.py` → `mpv --fs --vo=gpu --gpu-context=drm --ao=null
--video-rotate=270 --hwdec=auto ...` (holds /dev/dri/card0). So production uses **vo=gpu**
(GL) + 270° rotation; `--hwdec=auto` currently resolves to software (no v4l2request in the
stock ffmpeg) — the root cause.

## Findings
1. **vo_drm has the zero-copy KMS path on this HW**: mpv vo_drm logs
   `Using overlay plane 32 as drmprime plane` — a DRM overlay plane is available to scan
   out decoder dmabufs without GL. So a zero-copy `--vo=drm` overlay is feasible on this
   panfrost/sun4i display engine.
2. **mpv's v4l2request *hwdevice* creation fails in the shared-lib build**:
   `[vd] Looking at hwdec h264-v4l2request... Could not create device.` → falls back to
   software, for BOTH `v4l2request` and `-copy`, and **independent of the VO** (also fails
   with vo=null). Yet the *standalone* ffmpeg CLI created the same device fine in B1
   (`-init_hw_device v4l2request:/dev/media0`, decoded 240f @24× CPU). Patching the mpv
   shim to pass an explicit `/dev/media0` (instead of NULL) did **not** fix it ⇒ the bug is
   in the fork's `v4l2request` hwdevice `device_create` as exercised through mpv's
   shared `libav*` path. Devices are present/free/root-accessible (`/dev/media0`,
   `/dev/video0` = root:video 0660, 0 holders). This is a source-level integration bug to
   resolve in the image round (proper build env + ffmpeg debug logging).
3. **Production display = vo=gpu** needs a **GL-enabled** libplacebo+mpv (EGL/GBM/GLES) —
   the B3 libplacebo was built GPU-less. Not rebuilt here (would also require taking the
   board's KMS while live). vo_gpu is the existing player's VO, so it is the natural target.

## Net assessment
The CORE solution is **proven**: B1 shows the exact decode engine (ffmpeg + v4l2request)
HW-decodes real 1080p High/CABAC/B-frame content on this board at **~24× less CPU**
(0.41 s vs 9.98 s) — eliminating the loadfile CPU saturation that causes
`media_load_failed`. The remaining work is **player display integration**:
- (a) fix the v4l2request hwdevice creation through mpv's libav* path,
- (b) build the GL-enabled stack so `--hwdec=v4l2request --vo=gpu` (or `--vo=drm` overlay)
  does zero-copy `drm_prime → panfrost` with 270° rotation,
- (c) `totem` in `video` group, validate on a TEST board, package the image.
These are squarely the **image-lab round**, best done in a **Bookworm GCC-12 chroot**
(removes the B3 libstdc++ shim entirely). No fundamental blocker remains.

## Decision
```
B4_decision = DECODE_PROVEN_DISPLAY_IS_IMAGE_ROUND_INTEGRATION
zero_copy_kms_path_exists = true (vo_drm drmprime overlay plane)
mpv_v4l2request_hwdevice_create = FAILS via shared libav* (works in standalone ffmpeg) -> fix in image round
production_vo = gpu (drm) ; needs GL-enabled libplacebo+mpv (not built here)
core_solution_proven = true (B1 24x) ; limitation_C_accepted = false
```

## Guardrails
```
image_built=false flash=false install_on_board=false release_published=false
client_board_deploy=false board_temp_files_removed=true
kiosky-player stopped+restarted around display tests; final: player=active card0_holders=1 hdmi=connected video0 free
board_persistent_state_unchanged_by_us=true config/kernel untouched
limitation_C_accepted=false poc_commits_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
```
