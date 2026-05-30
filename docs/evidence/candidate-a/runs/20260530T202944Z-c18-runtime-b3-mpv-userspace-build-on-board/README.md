# C18.RUNTIME.B3 — full mpv userspace stack cross-built + HW decode engaged on board

The user chose "build the userspace stack now (no flash)". Done: the **entire media
userspace** was cross-compiled for the board and **mpv runs on the board driving the
Cedrus HW decoder**. No image/flash/install; bundle ran from `/tmp`, then removed.

## What was built (all cross-compiled, dynamic, board-ABI-matched)
ffmpeg-fork (shared) + **fribidi 1.0.13** + **freetype 2.13.3** + **libass 0.13.7**
(no harfbuzz/fontconfig → C-only) + **libplacebo 6.338.2** (all GPU backends off) +
**mpv `8670d2e`** (`Kwiboo/mpv@v4l2request-test-20240808`). All installed to one prefix,
bundled (12 MB), pushed to `/tmp` on the board with `LD_LIBRARY_PATH`.

mpv on the board:
```
mpv 8670d2e ... built on May 30 2026
--hwdec=help:  v4l2request (h264-v4l2request)   v4l2request-copy (h264-v4l2request-copy)  [+hevc,mpeg2]
```
HW decode **engages** (verbose, real content): `Trying hardware decoding via
h264-v4l2request-copy` → decoder pixfmts `drm_prime yuv420p` → `Requesting pixfmt
'drm_prime'`. i.e. mpv drove libavcodec's V4L2-Request hwaccel → Cedrus → drm_prime.

## Toolchain hurdle solved (key for the image round)
Host is **Ubuntu 24.04 (GCC 13 / glibc 2.39)**; board is **Bookworm (GCC 12 / glibc
2.36)**. C builds link fine against the Bookworm sysroot, but the GCC-13 cross
`libstdc++.a` references `__isoc23_strtoul` (glibc ≥2.38), absent on the board. Fixes:
- libass built **without harfbuzz** (0.13.7) ⇒ removes the only C++ in that subtree;
- libplacebo (unavoidable C++ via `fast_float`) built with **`-static-libstdc++
  -static-libgcc` + a tiny `__isoc23_*` compat shim** (`isoc23_compat.o`, included here)
  ⇒ `libplacebo.so` NEEDS only libc/libm, runs on glibc 2.36;
- relocated GCC-13 g++ wrapped to always pass `-B<xbin>` (cross `as`/`ld` symlinks) +
  `--sysroot` + `-fno-use-linker-plugin` (meson's bare `has_argument` checks otherwise
  invoked the host assembler). See `BUILD.md`, `cross.ini`, `isoc23_compat.c`.
The cleaner long-term route is to build inside a **Bookworm (GCC-12) container/chroot**,
which removes the shim entirely — recommended for the image round.

## Measured (mpv, board, 1080p High/CABAC/B-frames, 300 frames, `--untimed --vo=null`)
| mpv path                        | wall  | user CPU | sys  | note |
|---------------------------------|------:|---------:|-----:|------|
| `--hwdec=no` (software)         | 4.77s |  11.5s   | 0.36s| ~2.7 cores |
| `--hwdec=v4l2request-copy`      |10.98s |  10.5s   | 0.35s| HW decode **+ readback** |
| `--hwdec=v4l2request` (no-copy) | 4.70s |  11.5s   | 0.34s| vo_null can't import dmabuf ⇒ **falls back to SW** |

**Interpretation (important):** with a *null* VO you cannot measure the clean win at the
mpv level — non-copy needs a dmabuf-importing VO, and `-copy` pays a large **uncached
dmabuf readback** (~900 MB of NV12 read back over 300 frames) that the production path
never incurs. The clean HW-decode cost is the **B1 libavcodec figure: 0.41 s vs 9.98 s
software (~24×)**, measured with `-hwaccel_output_format drm_prime` (zero readback) —
mpv uses that *identical* hwaccel code. So:

## Production finding (steers the image round)
The totem player MUST use the **zero-copy display path**: `--hwdec=v4l2request --vo=gpu`
(or `--vo=drm`) with `--gpu-context=drm`, so decoded drm_prime dmabufs go straight to
the **panfrost** GPU/KMS with no CPU readback. `v4l2request-copy` is a fallback only and
largely negates the CPU win. Validating that zero-copy `drm_prime → panfrost` display is
the next item (the "display" round; needs EGL/GBM in libplacebo+mpv — not built here to
avoid grabbing the board's KMS while the player is live).

## Decision
```
B3_decision = MPV_HWDECODE_ENGAGES_ON_BOARD ; userspace stack cross-built end-to-end
clean_decode_win = 24x (B1 libavcodec, shared by mpv); copy-path adds readback
production_config = --hwdec=v4l2request --vo=gpu/drm (zero-copy to panfrost) ; NOT -copy
remaining = validate zero-copy drm_prime->panfrost display + package TEST image (gated)
limitation_C_accepted = false
```

## Guardrails
```
image_built=false flash=false install_on_board=false release_published=false
client_board_deploy=false board_temp_files_removed=true video0_holders_after=0
display/KMS_not_grabbed=true (vo=null only) board_persistent_state_unchanged_by_us=true
limitation_C_accepted=false poc_commits_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
```
