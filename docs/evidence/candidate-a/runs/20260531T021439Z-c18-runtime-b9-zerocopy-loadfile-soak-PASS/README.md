# C18.RUNTIME.B9 — zero-copy loadfile-transition soak: ZERO_COPY_LOADFILE_SOAK_PASSED

The original `media_load_failed` is born at the **media transition** (`loadfile`), not at
steady playback. This soak proves the custom stack survives **repeated transitions under
the most aggressive stress** without the phenomenon. No image/flash; ran from `/tmp`;
player stopped/restarted with a safety-net and **fully restored**.

## Setup
Custom mpv (idle + IPC), exact production VO shape:
`--vo=gpu --gpu-context=drm --hwdec=v4l2request --video-rotate=270 --input-ipc-server=...`.
A Python IPC driver (`dadooh_soak.py`, archived) sent `loadfile <clip> replace` every ~2 s,
cycling **3 clips of different resolution/fps/profile** (1080p30 High, 720p30 High,
1080p25 Main) to force a GPU/VO reconfig + decoder reinit on every transition. It measured
the loadfile **ACK round-trip** (the exact metric behind `media_load_failed`: the player
declares failure if the loadfile IPC ACK doesn't return within 2 s), `file-loaded` time,
`hwdec-current`, stalls, IPC errors, and mpv CPU (`/proc`).

## Result — 30 min, 867 transitions
```
ack_ms avg=1.5  p95=6  max=13            (threshold = 2000 ms; never approached)
ack_timeouts_gt2s=0  load_timeouts_gt2s=0  stalls_no_fileloaded=0  ipc_errors=0
hwdec_samples={'v4l2request': 867}  hwdec_lost_not_v4l2request=0
mpv_cpu_s=363.9  => 20.2% of one core (sustained, under constant transitions)
ZEROCOPY_CHECK=PASS (no autoconvert/HW-download anywhere in the mpv log)
RESULT=ZERO_COPY_LOADFILE_SOAK_PASSED
SOAK_DONE player=active card0=1 hdmi=connected   (board restored)
```

## Success criteria (user's) — all PASS
- hwdec stays engaged ......................... PASS (867/867 v4l2request, 0 drops to software)
- drm_prime / zero-copy stays active ......... PASS (no autoconvert/HW-download in the whole log)
- 270° rotation stays active ................. PASS (ran with --video-rotate=270 throughout)
- loadfile ACK never exceeds the timeout ..... PASS (max 13 ms vs 2000 ms)
- no media_load_failed equivalent ............ PASS (0 ack/load timeouts)
- CPU stays low .............................. PASS (20.2% of one core under constant transitions)
- sequence advances without freeze/restart ... PASS (0 stalls, 0 crashes, 867 clean transitions)
- board restored ............................. PASS

## Why this is decisive
This is the **worst case**: back-to-back transitions every ~2 s, each forcing a full
GPU/VO reconfig across three different resolutions + a decoder reinit — far harsher than
real playback (where each item plays its full duration between transitions). The software
path saturated 3+ cores and blew the 2 s IPC timeout *exactly here* (the root cause). The
HW/zero-copy path does it at 20% of one core with millisecond ACKs and not a single
failure. **The media_load_failed root cause is eliminated under transition stress.**

## Classification
```
B9 = ZERO_COPY_LOADFILE_SOAK_PASSED
transitions=867 duration=30min ack_max=13ms timeouts=0 hwdec_lost=0 stalls=0 cpu=20.2%/core
zero_copy_held=true rotation270=true board_restored=true
```
Next: the image-lab round (see IMAGE-LAB-PLAN.md) — gated on physical flash access.

## Guardrails
```
image_flashed=false live_board_overwritten=false install_on_board=false release=false config_real_change=false c12_touched=false client_board=false
kiosky-player stopped+restarted around the soak (safety-net guaranteed restart); final: player=active card0 held hdmi=connected video0 free tmp clean
limitation_C_accepted=false poc_commits_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
```
