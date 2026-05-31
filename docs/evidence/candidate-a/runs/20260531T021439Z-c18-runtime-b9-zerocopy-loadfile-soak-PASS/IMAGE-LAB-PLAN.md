# C18.RUNTIME — Image-lab round plan (productize the proven HW-decode fix)

Status going in: the fix is **technically proven end-to-end on the real hardware** —
Cedrus HW decode → zero-copy drm_prime → panfrost display (overlay / EGLImage) → 270°
rotation → low CPU, and it **survives 867 loadfile transitions / 30 min with 0
media_load_failed and 20% of one core** (A2, B1–B9). What remains is packaging + a physical
flash, which this round covers. **This round requires physical access to a board** (the only
unit available is the live remote one; it cannot be safely flashed over SSH).

## 0. Guardrails (carry over)
No client-board deploy; flash a TEST board only; keep PoC artifacts on
`c18-runtime-a1-cedrus-hwdecode-poc`; foundation receives only the final
shipping change once validated; password never persisted; sanitized evidence;
do not accept limitation C; keep a known-good image to re-flash on failure.

## 1. Build environment — Bookworm GCC-12 chroot (removes the B3 libstdc++ shim)
Build the whole stack inside a Debian **Bookworm arm64** chroot (qemu-user-static +
debootstrap, or a native arm64 builder). Rationale: the host used for the PoC was Ubuntu
24.04 (GCC-13/glibc-2.39), which forced a static-libstdc++ + `__isoc23_*` shim (B3) and a
GL header scramble. A Bookworm/GCC-12 toolchain matches the board exactly → no shim, clean
dynamic linking, distro-native packaging. Everything below then builds with the distro's
own toolchain and dev packages (libdrm-dev, libudev-dev, libegl-dev, libgles-dev,
libgbm-dev, libplacebo build-deps), so the B1/B3 sysroot gymnastics disappear.

## 2. Userspace stack (proven components + versions)
- **ffmpeg fork**: `github.com/Kwiboo/FFmpeg @ v4l2request-2024-v2` — configure with
  `--enable-v4l2-request --enable-libdrm --enable-libudev` + the codecs/filters/muxers the
  player needs (not the minimal PoC set). (B1 recipe.)
- **libplacebo** ≥ 6.338.2 with `-Dopengl=enabled`. (B7.)
- **libass / freetype / fribidi / harfbuzz** from the distro (chroot has them; no
  no-harfbuzz workaround needed). (B3 used libass-0.13.7-no-harfbuzz only due to the host
  C++ limit — drop that in-chroot.)
- **mpv**: `github.com/Kwiboo/mpv @ v4l2request-test-20240808` (or rebase onto a release
  carrying philipl PR #14690), built `-Dv4l2request=enabled` + egl/gbm/gl/drm (the
  `v4l2request` and `v4l2request-overlay` ra_hwdec interops). (B2/B7.)
- The B6 one-line `vd_lavc.c` device fallback is NOT needed for the vo=gpu path (the
  `v4l2request`/`v4l2request-overlay` ra_hwdec interops create the device); keep mpv stock.

## 3. Player config change (the actual product wiring)
- `kiosk.py` / launcher: change the mpv args from `--hwdec=auto` to
  **`--hwdec=v4l2request`** (keep `--vo=gpu --gpu-context=drm --video-rotate=270 --ao=null
  --force-window=yes` etc.). `auto` currently resolves to software = the bug.
- Keep the C18.2 IPC baseline (no soft-retry); with HW decode the loadfile ACK is ~ms (B9),
  so the 2 s timeout has enormous margin.
- This is the kiosky-player `appliance-v0.1` change; ship it only after TEST-board validation.

## 4. System integration
- Add the `totem` user to the **`video`** group (access to `/dev/video0`, `/dev/media0`,
  `/dev/dri/*`). Verify the udev/group perms survive reboot and the C11 read-only/overlay.
- Package the built `libav*`, libplacebo, mpv (+ runtime deps) into the image; ensure the
  loader finds them (distro paths, not LD_LIBRARY_PATH).
- Confirm the kernel keeps the Cedrus + panfrost drivers (it does on 6.12.58-sunxi64).

## 5. Image assembly
- Build the candidate image via the existing C12/C17 image-lab pipeline, adding the stack +
  the player config change. Keep read-only/overlayroot (C11/C12) intact.
- Produce the image as a file; record its hash; keep the current known-good image for rollback.

## 6. Validation on a TEST board (physical)
Flash the candidate to a TEST board (NOT a client board), then:
- **Engagement**: player mpv logs `Using hardware decoding (v4l2request)` + `v4l2request`
  /`v4l2request-overlay` interop; `hwdec-current=v4l2request`.
- **Zero-copy**: no `[autoconvert] HW-downloading` in the mpv log.
- **Visual (human eyes on HDMI)**: correct image, correct 270° orientation, no tearing/black
  frames across transitions. (The one thing not verifiable remotely.)
- **Steady real-time fps**: confirm smooth 30 fps at real-time (the PoC `--untimed` throughput
  artifact ~11 fps is not the real-time ceiling; verify it sustains content fps).
- **Soak / no regression**: re-run the B9-style loadfile soak in-image (or real playlist) for
  ≥25 min: `media_load_failed`≈0, hwdec stays engaged, CPU low. The standalone B9 already
  showed 0/867; confirm under the real kiosk.py IPC path.
- **CPU headroom**: confirm idle/playback CPU is a small fraction of one core (vs the prior
  software ~300%+ during transitions).

## 7. Pass / fail
- PASS ⇒ ship the player-config change to `appliance-v0.1` (and the image to the homolog
  channel), then a controlled rollout. Update C18.RUNTIME docs on `foundation-v0.1`.
- FAIL ⇒ classify (visual? rotation-on-overlay? fps? perms? packaging?) and iterate in-lab;
  re-flash the known-good image to restore the TEST board. Do not accept limitation C.

## 8. Open items / risks (small, bounded)
- **270° on the overlay plane**: at rotation, mpv uses the EGLImage GL path (B8) — confirm
  the GL-composited 270° output is correct and within the panfrost fill-rate at real-time.
- **Mode/resolution**: the test HDMI negotiated 1360×768; confirm the production panels'
  modes behave (the overlay SRC/CRTC scaling).
- **harfbuzz/libass in-image** (full subtitle/OSD) vs the PoC minimal libass — distro build
  removes that limitation.
- **Update channel**: ship via the C14 GitHub-releases pull path; ensure the R4 updater-perms
  fix (separate branch) lands so pulled releases actually run.

## Evidence trail (all on the PoC branch)
A1 (probe) · A2 (userspace decode) · B1 (ffmpeg 24× CPU) · B2 (mpv integration) ·
B3 (full stack cross-build) · B4/B5/B6 (display root-cause + mpv patch) ·
B7 (zero-copy display PROVEN) · B8 (270° rotation PASS) · **B9 (loadfile soak PASS)**.
Reproducible recipes: B1 `BUILD.md`, B3 `BUILD.md`, B7/B8 notes, B9 `dadooh_soak.py`.
