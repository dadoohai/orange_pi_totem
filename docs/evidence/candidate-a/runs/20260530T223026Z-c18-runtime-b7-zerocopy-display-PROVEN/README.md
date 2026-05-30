# C18.RUNTIME.B7 — zero-copy HW-decode + display PROVEN on the board (vo=gpu)

The last technical link is now proven: a cross-built mpv on the production board
**hardware-decodes (Cedrus/v4l2request) AND displays the decoded dmabuf zero-copy on the
panfrost KMS overlay (vo=gpu --gpu-context=drm), on the actual HDMI, at ~7× less decode
CPU — with no software fallback and no readback.** No image/flash/install; ran from
`/tmp`; the live player was stopped/restarted and is fully restored.

## What was built to get here (this round)
Rebuilt **libplacebo** with `-Dopengl=enabled` and **mpv** with EGL/GBM/GL enabled
(features: `egl egl-drm gbm gl gpu dmabuf-interop-gl drm libplacebo v4l2request`).
GL headers from Debian Bookworm `libegl-dev`/`libgles-dev` + `KHR/khrplatform.h` from the
Khronos registry; GL runtime libs (libEGL/libgbm/libGLdispatch/libglapi) pulled from the
board itself (exact ABI). mpv links `libEGL.so.1 + libgbm.so.1` (board mesa) and loads GL
via EGL. (Recipe extends B3 BUILD.md.)

## Proof (board, verbose + benchmark)
```
[vo/gpu] Loading hwdec driver 'v4l2request-overlay'
[vo/gpu/v4l2request-overlay] Using primary plane 38 as draw plane
[vo/gpu/v4l2request-overlay] Using overlay plane 32 as drmprime plane
[vd] Using hardware decoding (v4l2request).
[vd] Decoder format: 1920x1080 drm_prime[nv12] ...
[vf] [in]/[userdeint]/[autorotate]: 1920x1080 drm_prime[nv12]   <-- stays drm_prime, NO autoconvert download
```
EGL/GL came up on panfrost: `EGL_VENDOR=Mesa`, `Detected desktop OpenGL 3.1`,
GBM surface, overlay plane 32.

CPU — same 1080p High/CABAC/B-frame clip, 300 frames, `--vo=gpu --gpu-context=drm
--untimed`, on HDMI:
| path | user CPU | sys | total | vs SW |
|---|---|---|---|---|
| SW (`--hwdec=no`)          | 13.3 s | 1.7 s | ~15.0 s | — |
| HW (`--hwdec=v4l2request`) | **1.9 s** | 1.5 s | **~3.4 s** | **~7× less decode CPU, ~4.4× total** |

## Success criteria (user's) — result
- custom mpv runs on board ............................ PASS
- hwdec=v4l2request engages .......................... PASS (`Using hardware decoding (v4l2request)`)
- does NOT fall back to software ..................... PASS (drm_prime path, no SW)
- zero-copy/drm_prime used (observable) .............. PASS (frames stay drm_prime to the v4l2request-overlay; no `[autoconvert] HW-downloading`)
- HDMI displays correctly ............................ RAN end-to-end on the connected HDMI via overlay plane, no errors; **visual correctness needs a human looking at the screen** (cannot verify remotely)
- CPU low ............................................ PASS (1.9 s vs 13.3 s user)
- no media_load_failed/IPC stall during test ........ PASS (standalone mpv; decode did not stall)
- board restored ..................................... PASS (player active, card0 held, hdmi connected, temp files removed)

## Honest classification — what this DOES and does NOT prove
PROVES: the full chain works on this exact hardware — Cedrus stateless HW decode →
drm_prime dmabuf → zero-copy scanout on the panfrost overlay plane via vo=gpu, at low CPU.
The media_load_failed root cause (software-decode CPU saturation) is removed end-to-end.

Does NOT yet validate (image-lab round, needs physical flash):
- **Production config wiring**: `kiosk.py` must launch mpv with `--hwdec=v4l2request`
  (today it uses `--hwdec=auto` = software). Trivial config change, validated in-image.
- **270° rotation**: production uses `--video-rotate=270`. The video here is on a KMS
  **overlay plane** (bypassing GL); KMS plane rotation on sun4i may be unsupported → may
  force a GL-composite path (vo=gpu without the overlay interop, sampling the dmabuf as an
  EGLImage and rotating in shader — still zero-copy readback-wise, slightly more GPU). MUST
  be checked in the image round.
- **Sustained real-time fps**: under `--untimed` both SW/HW hit ~11 fps wall (display/GL
  draw-plane throughput artifact, not decode-bound — CPU was the differentiator). Confirm
  steady 30 fps at real-time in-image.
- **Visual correctness** (human eyes) and a **soak** (media_load_failed≈0 ≥ ≥25 min).

## Guardrails
```
image_flashed=false live_board_overwritten=false install_on_board=false release=false
kiosky-player stopped+restarted around the HDMI test; final: player=active card0 held hdmi=connected video0 free tmp clean
board_persistent_state_unchanged_by_us=true config/kernel untouched ; display/KMS released back to the player
limitation_C_accepted=false poc_commits_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
```
