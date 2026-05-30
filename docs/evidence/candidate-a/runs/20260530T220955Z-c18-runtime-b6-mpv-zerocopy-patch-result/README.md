# C18.RUNTIME.B6 — mpv zero-copy patch attempt: HW decode now engages, display download remains

Per the user's choice ("patch mpv + validate zero-copy, no flash"), I patched mpv and
validated on the live board via `/tmp` (player stopped/restarted around display tests;
fully restored). Result: the patch **fixes HW-decode engagement through mpv**, and
**pinpoints the exact remaining blocker for zero-copy display**.

## The patch (`mpv-vd_lavc-v4l2request-device-fallback.patch`, included)
`video/decode/vd_lavc.c : hwdec_create_dev()` — when the non-copy path's VO-interop
lookup misses (it always does for `v4l2request`, since VOs register their drm_prime
interop under `AV_HWDEVICE_TYPE_DRM`), fall back to creating the v4l2request device
standalone (`av_hwdevice_ctx_create(V4L2REQUEST, "/dev/media0")`).

## Result — two parts
**(1) FIXED: HW decode now engages through mpv (non-copy).** Verbose on the board:
```
[vd] Trying hardware decoding via h264-v4l2request.
[vd] Requesting pixfmt 'drm_prime' from decoder.
Using hardware decoding (v4l2request).
[vd] Decoder format: 1920x1080 drm_prime[nv12] ...
```
No more "Could not create device" — the device is created and the VPU decodes to
drm_prime[nv12]. (Confirmed with vo=null and vo=drm.)

**(2) STILL OPEN: zero-copy *display*.** With `--vo=drm --hwdec=v4l2request`, mpv inserts:
```
[autoconvert] HW-downloading from drm_prime
```
i.e. mpv **downloads** the decoded dmabuf to a software frame and draws it on the primary
plane, instead of scanning out the dmabuf on vo_drm's **drmprime overlay plane** (which
vo_drm *did* allocate: `Using overlay plane 32 as drmprime plane`). So CPU stays high:

| vo=drm, 300f, untimed | wall | user CPU |
|---|---|---|
| SW (`--hwdec=no`)             | (timeout 35s cap) | 39.8s |
| HW (`--hwdec=v4l2request`)    | (timeout 35s cap) | 39.6s |

(Both capped by the readback/download path; no zero-copy benefit realized at the VO yet.)

## Exact remaining work (sharpened from B5)
The decode-device creation is solved (this patch). The remaining blocker is the
**VO↔hwdec frame-delivery interop**: mpv's autoconvert downloads drm_prime because no VO
hwdec-interop claims the `v4l2request` frames, so mpv's format negotiation thinks the VO
needs software input. To get zero-copy the image round must wire the interop so mpv routes
drm_prime frames straight to:
- **vo_drm**: its drmprime overlay plane (register a vo_drm hwdec interop that accepts the
  `v4l2request` drm_prime frames → no autoconvert download), or
- **vo_gpu** (production VO): the EGLImage dma-buf import interop (needs the GL-enabled
  libplacebo+mpv build) so the panfrost GPU samples the dmabuf directly.
This is the intent of mpv PR #14690; it is multi-file mpv work (interop registration +
format negotiation), best iterated in the image round.

## Bottom line
- **Decode is proven and now engages through the real player** (mpv): VPU decodes real
  1080p High/CABAC content to drm_prime. The CPU win itself is B1's **~24×** (libavcodec,
  zero readback) — the engine mpv uses.
- The last gap is purely **frame-delivery interop to the display VO** (so mpv stops
  downloading) — a known, localized-to-mpv integration task for the image round, plus the
  physical flash (sole live board → needs physical access / spare).

## Guardrails
```
image_flashed=false live_board_overwritten=false
kiosky-player stopped+restarted around display tests; final: player=active card0 held hdmi=connected video0 free tmp clean
board_persistent_state_unchanged_by_us=true ; patch applied only to the /tmp test mpv (removed)
limitation_C_accepted=false poc_commits_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
```
