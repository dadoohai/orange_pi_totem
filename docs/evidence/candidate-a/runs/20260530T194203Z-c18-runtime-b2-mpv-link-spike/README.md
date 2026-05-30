# C18.RUNTIME.B2 — mpv ↔ ffmpeg-V4L2-Request link spike (no flash)

Goal: prove the **player engine (mpv)** can HW-decode via the Route-B ffmpeg fork.
Outcome: the mpv↔fork **integration is confirmed feasible and trivial**; producing a
**runnable** mpv binary is gated on building mpv's mandatory display-dependency stack
(libplacebo + libass + freetype/fribidi…), which is the same userspace build the
image round performs — there is no lightweight shortcut.

## What was confirmed (cheap, definitive)
- Matched mpv branch = `github.com/Kwiboo/mpv @ v4l2request-test-20240808` (HEAD 8670d2e),
  pairs with the B1 ffmpeg fork `Kwiboo/FFmpeg @ v4l2request-2024-v2`.
- mpv's meson gate for the feature is exactly:
  `cc.has_header_symbol('libavutil/hwcontext.h', 'AV_HWDEVICE_TYPE_V4L2REQUEST')`.
  The fork's header exports that symbol (`libavutil/hwcontext.h:41`) ⇒ **`-Dv4l2request`
  will be ENABLED** when mpv is built against this ffmpeg.
- mpv's hwdec shim (`video/v4l2request.c`) is a thin wrapper that calls
  `av_hwdevice_ctx_create(&ref, AV_HWDEVICE_TYPE_V4L2REQUEST, …)` — i.e. it drives the
  **identical** hwdevice + drm_prime path already validated end-to-end in B1
  (ffmpeg CLI: 240 frames real High/CABAC content, ~24× less CPU on Cedrus).
  philipl PR #14690 splits this into `v4l2request` (display interop) and
  `v4l2request-copy` (download to RAM; works with `--vo=null`).
- ffmpeg fork was also rebuilt as **shared libs** (`--enable-shared`, installed to a
  prefix with `.pc` files) so mpv/the image can link against `libav*` — recipe extends
  B1's `BUILD.md`.

## Why a runnable mpv = image-round work (the scope finding)
- Modern mpv **hard-requires** `libplacebo (>=6.338.2)` and `libass (>=0.12.2)`
  (meson `dependency(...)` with no `required:false`); `libavdevice`/vulkan are optional.
- mpv ships **no dependency wraps** (`subprojects/*.wrap` is empty), so meson will not
  auto-fetch/build them — each must be cross-built by hand.
- The board image is **Minimal**: it has none of libplacebo/libass/freetype/fribidi at
  runtime, so they must be built AND shipped.
- The cross-host has **no `g++`** (only `aarch64-linux-gnu-gcc`), so any C++ dep
  (e.g. harfbuzz) is out; a C-only chain is possible
  (fribidi → freetype-minimal → libass `--disable-harfbuzz --disable-fontconfig`
  → libplacebo `-Dvulkan/opengl/d3d11/shaderc/glslang=disabled` → mpv `--vo=null`)
  but that is ~5 cross-builds + mpv = the image round's userspace build, done early.

## Decision
```
B2_decision = MPV_INTEGRATION_CONFIRMED_BUILD_GATED
mpv_v4l2request_enabled_against_fork = true (header symbol present; shim trivial)
mpv_shim_path = av_hwdevice_ctx_create(AV_HWDEVICE_TYPE_V4L2REQUEST) == B1-validated path
runnable_mpv_blocker = mandatory libplacebo+libass (no wraps, none on Minimal board, no g++ cross)
=> equals the image round's userspace build; no lightweight shortcut
limitation_C_accepted = false
```

## Recommendation
The two hard technical risks are retired: (A2) Cedrus HW decode works from userspace;
(B1) a mature decoder HW-decodes real content at ~24× less CPU on the board; (B2) mpv's
hwdec rides that same validated path and will compile against the fork. The remaining
work — build libplacebo+libass(+freetype/fribidi)+mpv, then validate on a TEST board and
package — is the image-lab round. Either execute that userspace build now (no flash; run
`mpv --vo=null --hwdec=v4l2request-copy` on the board) or fold it into the planned image
round. Team decision.

## Guardrails
```
image_built=false flash=false install_on_board=false release_published=false
client_board_deploy=false board_persistent_state_unchanged_by_us=true
limitation_C_accepted=false poc_commits_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
```
