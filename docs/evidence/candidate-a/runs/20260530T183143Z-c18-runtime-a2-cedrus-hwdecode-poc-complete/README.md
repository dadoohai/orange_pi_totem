# C18.RUNTIME.A2 — Cedrus stateless H.264 HW decode: COMPLETE PoC (real frame decoded)

Continuation of A1 (which was only a *capability probe*). This round wrote a
from-scratch userspace stateless H.264 decoder, cross-built it for the board, and
**actually decoded frames on the production hardware** via the V4L2 Request API —
including at the real content resolution (1080p) — while measuring CPU.

All board interaction was read-only w.r.t. persistent state (own fds on
`/dev/video0`+`/dev/media0`, which the player does not use; temp files removed;
no service/config/kernel/image/release changes). Output sanitized.

## Decision (supersedes A1's A_BLOCKED_BUILD)
```
A2_decision = A_PROVEN_DECODE   (the HW decode path works end-to-end at the primitive level)
kernel_cedrus_ready   = true     (already known from A1)
userspace_decode_works = true    (NEW: a userspace program drives Cedrus stateless decode)
cross_build_toolchain  = solved  (NEW: A1's "no aarch64 sysroot / no board toolchain" blocker removed)
real_resolution_ok     = true    (NEW: 1080p IDR decodes correctly, ~5 ms/frame)
cpu_offloaded          = true     (NEW: ~5.6% of one core @30fps vs software ~300%+)
remaining_gap          = PLAYER INTEGRATION ONLY (a build/packaging round, not a research unknown)
limitation_C_accepted  = false
```

## What was built
`cedrus_h264.c` (archived here): a self-contained C decoder — Annex-B NAL scan,
exp-Golomb bit reader, SPS/PPS/baseline-I-slice parse, fills the V4L2 stateless
H.264 controls (SPS/PPS/SCALING_MATRIX/DECODE_PARAMS/SLICE_PARAMS/PRED_WEIGHTS),
and drives the Request API:
`MEDIA_IOC_REQUEST_ALLOC` → `S_EXT_CTRLS(WHICH_REQUEST_VAL)` →
`QBUF(OUTPUT, REQUEST_FD)` → `MEDIA_REQUEST_IOC_QUEUE` → poll → `DQBUF(CAPTURE)`.
Mode = `SLICE_BASED` + `START_CODE_NONE` (Cedrus only allows slice-based; this was
the A1→A2 fix — frame-based returned ERANGE). Cross-built static:
`aarch64-linux-gnu-gcc -static -O2 -isystem <sysroot>/include -B/-L <sysroot>/lib`
against a local sysroot assembled from upstream `.deb`s (no sudo, no apt on board).

## Measured result (on the board)
Inputs = synthetic baseline/CAVLC single-IDR clips (`profile_idc=66`), decoded in a
tight re-feed loop; CPU via `getrusage(RUSAGE_SELF)`.

| stream            | frames | avg decode | max decode | achievable fps | process CPU (user+sys)      |
|-------------------|-------:|-----------:|-----------:|---------------:|-----------------------------|
| 320x240 IDR       |    500 |   0.244 ms |   0.75 ms  |        ~3133   | 0.126 ms/frame (39% @3133fps)|
| **1920x1088 IDR** |    300 | **5.10 ms**|   8.03 ms  |       **~147** | 1.87 ms/frame (27.5% @147fps)|

- Decoded output is correct: `Y_mean=41.0` for a blue 320x240 frame (BT.601 limited
  range), `Y_mean=126.2` for a 1080p testsrc2 pattern. CAPTURE negotiated `NV12`.
- **CPU headline:** at the real 1080p resolution, decoding costs ~1.87 ms of process
  CPU per frame. Normalized to 30 fps playback that is **~5.6% of a single core** —
  versus the software-decode path that saturated 3+ cores (~300%+, the C18.RUNTIME.3
  finding) and produced the `loadfile` stall that triggers false `media_load_failed`.
  HW decode removes exactly the CPU pressure that is the root cause.

## Why this is the real solution mechanism (and what is NOT yet done)
This hand decoder is the **proof**, not the production player: it only parses
baseline/CAVLC. Real content (High profile, CABAC, B-frames) must be parsed by a
mature decoder — but that mature decoder would feed the **same** kernel path proven
here (`S264` slice → `NV12`, Request API, `/dev/video0`+`/dev/media0`).

The board has **no** userspace able to drive that path today (verified read-only this
round): GStreamer absent; mpv 0.35.1 / ffmpeg 5.1.8 expose only
`nvdec/vaapi/drm/...` hwaccels — **no `v4l2request`** — and Cedrus has no VA driver.
So the only remaining work is **player integration**, which requires building
software → an image/build-lab round (gated on a human go/no-go; involves a TEST
board flash). That is packaging, not a remaining technical unknown.

## Recommended productization routes (for the gated build round)
- **Route B (recommended, least app churn):** patched ffmpeg with the V4L2 Request
  hwaccel (the LibreELEC / `ffmpeg-v4l2-request` patchset, drm-prime frames) + keep
  mpv (`--hwdec=drm`). Preserves the existing mpv + `kiosk.py` IPC control plane.
- **Route A (cleanest upstream):** GStreamer + `v4l2codecs` (`v4l2slh264dec`,
  mainline) → `kmssink`. Changes the player engine (larger `kiosk.py` rework).
- Either way: `totem` user in the `video` group; validate on a TEST board
  (hwdec engages, `media_load_failed`≈0 over ≥25 min, CPU/visual ok on HDMI,
  soak ≥1 h). Pass ⇒ plan candidate image (separate round). No production deploy.

## Guardrails
```
image_built=false kernel_touched=false release_published=false backend_changed=false
real_config_changed=false apt_upgrade/install=false poweroff=false c12_readonly_touched=false
client_board_deploy=false player_service_touched=false board_temp_files_removed=true
board_persistent_state=unchanged
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
limitation_C_accepted=false poc_commits_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
```
