# C18.IMAGE-LAB.1c — `--no-osc` fix + LIVE hardware validation (C18.IMAGE-LAB.2)

The C18 HW-decode image is now **validated end-to-end on the board**. 1c is the canonical
clean image; the live board (running 1b + the in-place wrapper fix == 1c content) confirmed
HW decode playback. No card flashed here.

## The third (and final) root cause: `--no-osc`
After 1b fixed the kiosk.py SyntaxError + panfrost, the player still looped on
"iniciando player". Diagnosed on the board (player as `User=totem`):
```
[cplayer] Error parsing option no-osc (option not found)
Setting commandline option --no-osc= failed. Exiting... (Fatal error)
```
`kiosk.py build_mpv_args` passes `--no-osc` (valid in stock mpv 0.35.1). The custom mpv was
built `-Dlua=disabled` — the OSC is a Lua script, so the `--osc`/`--no-osc` option does not
exist → mpv **fatal-exits before creating the IPC socket** → the player's 10s IPC startup
times out → kill → relaunch (crash-loop). Confirmed read-only: with the full service args
**minus `--no-osc`**, mpv creates the socket in ~1s and vo=gpu+hwdec engage (no other
incompatible option).

**Fix (1c):** the wrapper `/opt/totem/bin/totem-mpv-hwdecode` now **strips `--no-osc`** from
the args before exec (no OSC in a no-Lua build, so dropping it is correct). Validation also
gained a `wrapper_strips_no_osc` check.

## LIVE hardware validation (board 192.168.18.131, fix applied in-place — user authorized)
After applying the fixed wrapper + restarting kiosky-player:
```
socket=UP   mpv stable (single pid, generation=1, ~3 min, no relaunch)
hwdec-current = v4l2request          <-- HW decode engaged on real content
video-codec   = H.264 / AVC          width=360 height=640  ~24 fps  core-idle=False (playing)
playback_state = playing             playlist: 8 items, transitioning index 4->5->6->7->0->1
media_load_failed (this boot) = 0    <-- ROOT CAUSE ELIMINATED across loadfile transitions
mpv CPU ≈ 13.6%  (one core; software decode previously saturated 3+ cores)
```
The loadfile transitions (the original `media_load_failed` trigger) happen on a single
stable mpv with **zero** failures. (Visual correctness on the HDMI to be confirmed by a
human; all telemetry = playing with HW decode.)

## Persistence (fewer flash cycles)
Root `/` is **ext4 rw** and `overlayroot=tmpfs` is in the cmdline but **NOT active**
(findmnt shows plain ext4; writes persist — consistent with C12 read-only never being
shipped/activated). So the in-place wrapper fix **persists across reboot** → the board works
now and stays working; **no urgent re-flash needed for this board**.

## Image (canonical, clean — for records / future flashes)
```
image=Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1c_minimal.img
sha256=766a3eb2071e599df5561918c8308f9559fb8d24ee65168839a8cf6a75d85c29
supersedes=c18-hwdecode-lab-1 (kiosk.py banner) & 1b (--no-osc) — both removed from output/images
artifact_private=true final_image=false not_for_production=true ; offline_validation_passed=true
kernel/u-boot/dtb/c12_readonly untouched ; base_image_line=c17.4.2
```
1c == the content validated live (only the wrapper differs from 1b, and that wrapper is the
one validated on the board). Flash 1c only if a pristine/canonical image is wanted; the
running board already has the fix.

## The 3 defects found+fixed in C18.IMAGE-LAB.2 (all my deriver bugs; HW stack always fine)
1. (1→1b) kiosk.py corrupted by reading via debugfs `cat` (stderr banner appended) → read via `dump` + `py_compile` check.
2. (1→1b) panfrost `-110` deferred-probe race at boot → `totem-panfrost-rebind` oneshot service (userspace).
3. (1b→1c) player's `--no-osc` fatal on the no-Lua mpv → wrapper strips it.

## Secondary observations (non-blocking; for later)
- Boot ~2 min (kernel 30s + userspace 1m41) with a black screen before the wizard — slowish;
  can optimize later (panfrost deferred-probe window + firstboot). Terminal-flash at boot did
  NOT recur on 1b/1c (wizard came up without exposing a console).

## Guardrails
```
card_written=false image_flashed_here=false kernel/u-boot/dtb/c12_readonly_touched=false
in-place board change=wrapper only (user-authorized; persists on writable ext4); secrets/real-config=not embedded
limitation_C_accepted=false
```
