# C18.RUNTIME.B8 — 270° rotation + zero-copy: PASS (full production path validated)

The biggest remaining production unknown is resolved: the full production-shaped command
`--vo=gpu --gpu-context=drm --hwdec=v4l2request --video-rotate=270` runs on the board's
HDMI, HW-decodes via Cedrus, stays zero-copy, **and** applies 270° rotation — all at low
CPU. No image/flash; ran from `/tmp`; player stopped/restarted and fully restored.

## How rotation is handled (the key question answered)
mpv loads several drm_prime hwdec interops and picks per-need:
```
[vo/gpu] Loading hwdec driver 'v4l2request'           -> Using EGL dmabuf interop via GL_EXT_EGL_image_storage
[vo/gpu] Loading hwdec driver 'v4l2request-overlay'   -> KMS overlay plane
[cplayer] Setting option 'video-rotate' = '270'
```
- Without rotation (B7): mpv uses **`v4l2request-overlay`** → dmabuf scanned out directly on
  the panfrost **KMS overlay plane** (no GL at all for the video).
- With `--video-rotate=270`: KMS overlay planes can't rotate on sun4i, so mpv uses the
  **`v4l2request` EGL interop** → imports the decoder dmabuf as a **GL texture via
  `GL_EXT_EGL_image_storage`** (zero readback — the panfrost GPU samples the dmabuf
  directly) and rotates in the GL shader. Still zero-copy w.r.t. the CPU.

## CPU (300f, 1080p High/CABAC, vo=gpu --gpu-context=drm, --untimed, on HDMI)
| path | user CPU | sys | note |
|---|---:|---:|---|
| SW (`--hwdec=no`)                       | 13.3 s | 1.7 s | software decode |
| HW (`--hwdec=v4l2request`)              |  1.9 s | 1.5 s | overlay scanout (B7) |
| HW + **`--video-rotate=270`**           |  **2.2 s** | 1.7 s | EGLImage import + GPU shader rotation |

Rotation adds only ~0.3 s CPU (done on the GPU). A CPU readback would be ~10 s — it is not
happening, confirming zero-copy. ~6–7× less CPU than software, with rotation.

## Net: the production decode+display path is TECHNICALLY VALIDATED on the hardware
`--vo=gpu --gpu-context=drm --hwdec=v4l2request --video-rotate=270` (the exact shape the
kiosky-player mpv uses, but with `auto`→`v4l2request`):
- Cedrus HW decode ✓ · zero-copy dmabuf (overlay or EGLImage) ✓ · 270° rotation ✓ ·
  low CPU ✓ · on the connected HDMI ✓.

## Remaining (image-lab round; gated; physical flash)
- Wire `kiosk.py` to launch mpv with `--hwdec=v4l2request` (replacing `--hwdec=auto`).
- Package the cross-built stack (ffmpeg-fork + libplacebo + mpv + libass/ft/fribidi) into
  the image — ideally rebuilt in a **Bookworm GCC-12 chroot** (drops the libstdc++ shim).
- `totem` user in `video` group.
- **Visual correctness** (human eyes on HDMI) + **soak** (media_load_failed≈0 ≥25 min,
  steady real-time 30 fps) on a board with physical access.
- **Flash**: only one board exists and it's the live unit (SSH-only) → flash needs physical
  access or a spare; not done remotely.

## Guardrails
```
image_flashed=false live_board_overwritten=false install_on_board=false release=false
kiosky-player stopped+restarted around the HDMI test; final: player=active card0 held hdmi=connected video0 free tmp clean
board_persistent_state_unchanged_by_us=true ; display/KMS released back to the player
limitation_C_accepted=false poc_commits_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
```
