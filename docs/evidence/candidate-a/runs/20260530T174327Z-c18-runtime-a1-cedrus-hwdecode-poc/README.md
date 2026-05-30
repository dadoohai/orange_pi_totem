# C18.RUNTIME.A1 — Cedrus HW decode PoC (evidence)

PoC isolada (PDCA) na branch `c18-runtime-a1-cedrus-hwdecode-poc`. Tudo read-only
na placa; nada alterado; sanitizado. Log completo: POC_LOG.md naquela branch.

## Decision
A1_decision=A_BLOCKED_BUILD (cause=A_BLOCKED_STACK)
kernel_cedrus_ready=true
not_c_only=true (A viavel via rodada de imagem-lab; kernel pronto)

## Evidence (read-only)
ffmpeg=5.1.8 v4l2_decoders=stateful_v4l2m2m_only (no v4l2-request)
libva_present=true va_driver_for_cedrus=absent
gpu=panfrost cedrus=/dev/video0+/dev/media0
board_build_toolchain=none ; devhost_cross_gcc=present_but_no_aarch64_sysroot
v4l2_probe(/dev/video0): driver=cedrus is_m2m=1 streaming=1
  OUTPUT(coded-in)=[S264 H.264 slice, S265 HEVC slice, MG2S MPEG-2, VP8F]
  CAPTURE(decoded)=[NV12, ST12]
  h264_slice_stateless=true h264_stateful=false hevc_slice=true
=> Cedrus stateless-only; mainline ffmpeg stateful v4l2m2m cannot drive it
   (confirma o "Could not find a valid device" anterior).

## Next (unblock A) — image-lab round, NOT executed here
target=V4L2_stateless_H264_S264->NV12_via_Request_API + /dev/media0 (kernel 6.12.58-sunxi64)
need=downstream/patched ffmpeg (V4L2 stateless) + mpv linked to it; totem in video group
validate_on=TEST board: hwdec engages, media_load_failed~0 (>=25min), CPU/visual ok (HDMI eye), soak>=1h
pass=>plan candidate image (separate round); fail=>A_FAIL_RUNTIME, reopen A-vs-C

## Guardrails
image_built=false kernel_touched=false release_published=false backend_changed=false
real_config_changed=false apt_upgrade=false poweroff=false c12_readonly_touched=false
client_board_deploy=false board_state=read_only_unchanged(307d986/vo=gpu)
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
limitation_C_accepted=false poc_commits_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
