# C18.RUNTIME.B5 — zero-copy root-cause (mpv interop) + the flash constraint

The user authorized "execute the image round now (incl. flash a TEST board)". Two hard
realities bound what that means in this session; both are recorded here so the image
round is a precise, well-scoped task rather than open-ended.

## 1. Exact remaining code fix for zero-copy display (root-caused)
mpv `video/decode/vd_lavc.c : hwdec_create_dev()` has two branches:
```
if (hwdec->copying) {                 // v4l2request-COPY  -> uses the shim create_dev
    return fns->create_dev(...);      //   WORKS: this is the HW decode proven in B3
} else if (ctx->hwdec_devs) {         // v4l2request (NON-copy, zero-copy)
    hwdec_devices_get_by_imgfmt_and_type(imgfmt=drm_prime, type=hwdec->lavc_device);
    // ^ looks up a VO-registered hwdec interop keyed by hwdevice TYPE == "v4l2request"
}
```
The zero-copy path needs a VO interop registered for **type `v4l2request`**. vo_drm and
vo_gpu register their `drm_prime` overlay/EGL interop under type **`drm`**
(`AV_HWDEVICE_TYPE_DRM`), so the lookup misses → `hwdec_create_dev` returns NULL →
`MP_VERBOSE "Could not create device"` (vd_lavc.c:551) → software fallback. This is the
exact wiring philipl PR #14690 ("add separate hwdecs for v4l2request") addresses; the
`Kwiboo/mpv@v4l2request-test-20240808` branch used here doesn't fully wire vo_drm/vo_gpu
to the `v4l2request` type. **Fix = a localized mpv patch** so the VO drmprime interop is
offered for the `v4l2request` hwdevice type (or the non-copy path falls back to a
standalone `av_hwdevice_ctx_create(V4L2REQUEST,"/dev/media0")` and lets vo_drm scan out the
resulting drm_prime mp_images on its overlay plane — vo_drm already allocates that plane).
Confirmed not a hardware/driver issue: the **standalone ffmpeg created the device and
decoded fine (B1, 24×)**; libavutil's `hwcontext_v4l2request.device_create` is just
`open("/dev/media0")` and succeeds as root. `v4l2request-copy` works today but its uncached
dmabuf readback (~) negates most of the CPU win — so the interop fix (zero-copy) is required.

## 2. Flash constraint (must be resolved by the team)
There is **one board, and it is the live homologation unit**, reachable only over SSH.
- No physical SD access from here ⇒ cannot write/flash an image safely (and an in-place
  overwrite of the only board risks bricking it + losing the sole SSH access — irreversible).
- No separate spare/TEST board exists. The image-round validation plan assumes a TEST board.
⇒ The image **build** can be produced as a file here; the **flash + on-HDMI validation must
be performed with physical access** (or on a genuine spare board). I did NOT flash or
overwrite the live board.

## What IS proven / ready (recap)
A2 (Cedrus userspace decode) · B1 (**ffmpeg+v4l2request real-content HW decode, ~24× less
CPU on the board** — the decisive proof) · B2 (mpv build-gate integration) · B3 (full
userspace stack cross-built; mpv engages HW decode via `-copy`) · B4 (vo_drm has a drmprime
overlay plane). Reproducible recipes in B1/B3 `BUILD.md`.

## Image-round task spec (well-defined, gated on physical access)
1. Build the stack in a **Bookworm GCC-12 chroot** (drops the B3 libstdc++ shim).
2. Build **GL-enabled** libplacebo + mpv (EGL/GBM/GLES) for the production `--vo=gpu
   --gpu-context=drm --video-rotate=270` path.
3. Apply the **mpv interop patch** (§1) so non-copy `--hwdec=v4l2request` zero-copy engages
   (validate `Using hardware decoding` + low CPU end-to-end, no readback).
4. `totem` in `video` group; set the player `--hwdec=v4l2request` (replacing `auto`).
5. Validate on a **physical TEST board**: hwdec engages, `media_load_failed`≈0 ≥25 min,
   on-HDMI visual + 270° rotation, soak ≥1 h. Then ship the image.

## Guardrails
```
image_flashed=false live_board_overwritten=false remote_flash_attempted=false
board_persistent_state_unchanged_by_us=true (player active, hdmi connected, temp files removed)
limitation_C_accepted=false poc_commits_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
```
