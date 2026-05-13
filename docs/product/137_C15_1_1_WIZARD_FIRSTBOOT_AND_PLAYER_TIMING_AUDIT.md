# C15.1.1 — Wizard / first boot / F10 stabilization + player timing audit

Status: hotfix-deployed-and-instrumented; 1-of-2 on-device tests passed;
test #1 root cause **not classified** (`code=killed status=15/TERM` from
indeterminate source). Closure pending a deliberate validation battery
in `C15.1.2`.
Date: 2026-05-12 (hotfix v1) + 2026-05-13 (hotfix v2 instrumentation,
test #1 failure, test #2 success)
Branch: `foundation-v0.1`
Preceding card: `C14.2.1` (shipping homologation image with pull updater)
Follow-up card recommended: `C16.1.1` (player scheduler / sync audit)

## Why this card exists

After the C14.2.1 shipping homologation image started running on the lab
board, the operator reported two related families of symptoms:

P0 — wizard / first boot / F10:
1. Holding F10 sometimes opens the visual wizard but the screen "falls
   back" to the `config_missing` state.
2. On the first or second attempt the wizard can drop mid-configuration;
   the third attempt typically succeeds.
3. On the very first boot a terminal/login shell flashes briefly on the
   HDMI output before the wizard takes over.
4. Occasionally keystroke characters are visible on the corner of the
   screen, overlaying the SVG.

P1 — player:
1. A media sometimes appears to be stuck on loop.
2. The player sometimes appears to ignore the duration returned by the
   API.
3. There is a suspicion that the global sync logic conflicts with the
   straight sequential intent.
4. Operator request: do not refactor the player this round; first audit
   and collect evidence.

This card scopes the smallest set of safe, reversible changes that
explain and mitigate P0, plus the data-collection that prepares P1 for
a follow-up card.

## Restrictions explicitly preserved

- C12 read-only stays blocked.
- C12.4 / corte seco stays blocked.
- No `apt update / upgrade / full-upgrade / dist-upgrade / armbian-upgrade`.
- No `pip install` on the board.
- No kernel / U-Boot / DTB / BSP / rootfs change.
- No Wi-Fi / NetworkManager change.
- No Mender / RAUC / SWUpdate.
- No poweroff, no power-cut.
- No secrets published.
- SSH password never persisted in script/log/doc/evidence.
- Never print `api_key`, `api_url`, `environment_id`, SSID, Wi-Fi
  password, `private-values.seed.json`, or `/data/config/config.json`.

## Wizard pipeline (current state, audited)

1. `totem-settings-trigger.service` runs as a daemon and reads
   `/dev/input/event*` via the raw evdev struct
   (`struct.Struct("llHHI")`). It only detects long F10 (or optional
   Ctrl+I) holds. It never logs characters, codes, or values.
2. On a 5 s hold the trigger calls
   `systemctl start totem-open-settings.service`. The trigger respects
   a 10 s cooldown and a session lock at
   `/run/totem/settings-session.lock` (mkdir-style).
3. `totem-open-settings.service` ExecStartPre's:
   - `totem_visual_tty_guard.sh --clear --tty 2` — clears tty2, sets
     `stty -echo -icanon`, hides cursor.
   - `totem_settings_lab_apply_policy.sh
     --enable-from-homologation-seed-if-present
     --seed-path /data/state/totem-settings/private-values.seed.json
     --policy-path /run/dadooh-settings/apply-policy.json` — when the
     homologation seed marker is present, writes a policy file with
     `mode=real-write homologation_seed=true` so the wizard can write
     the real `/data/config/config.json` once the operator confirms.
4. `totem-open-settings.service` ExecStart: `totem_open_settings_session.sh`
   - takes `/run/totem/settings-session.lock` (mkdir lock; exits 23 if
     another session holds it);
   - stops `getty@tty1.service` and `getty@tty2.service` (idempotent;
     image already has both disabled);
   - `show_transition setup` — clears tty2 again and renders the
     "Setup" splash;
   - `systemctl stop kiosky-player.service` and waits up to 30 s for
     `kiosk.py`, `mpv`, the status renderer, and the visual wizard
     itself to drain;
   - runs the wizard as
     `setsid openvt -c 2 -s -f -w -- python3 totem_setup_visual_wizard.py`;
   - on exit: `restore_service` clears tty2, runs `show_transition
     player`/`config_pending`, then `systemctl start
     kiosky-player.service`;
   - cleans the lock and trigger request via ExecStopPost
     `totem_open_settings_cleanup.sh`.

## Symptom reproduction & classification

### wizard_exit_cause = `service_race_with_config_missing`

The 30-second `process_counts` wait in
`totem_open_settings_session.sh` returned non-zero counts on first
attempts. The launcher cascade
(`kiosky_service_launcher.sh` → `kiosk.py` → `mpv` plus a second
`bash kiosky_service_launcher.sh` subprocess seen in the running ps
table) did not always release tty2 / drain processes within 30 s after
`systemctl stop kiosky-player.service`. When the wait expired, the
script bailed out with `exit 42 hdmi_not_free_after_player_pause`,
which let `restore_service` restart `kiosky-player.service` and the
operator saw the splash "come back". A single matching journal entry
exists at `2026-05-12T11:04:04Z`:

> `Failed to start totem-open-settings.service - Dadooh Open Totem Settings.`

After residual processes had been reaped by the kernel, subsequent
attempts (the "third try") succeeded.

### tty_leak_cause = `renderer_starts_too_late`

`totem_firstboot_gate.sh` (lines 111–122) writes raw Portuguese text
directly to `/dev/tty2` before the splash python renders, on every
boot where `/root/.not_logged_in_yet` exists. On lab boards this
marker is removed by `totem-lab-firstboot-autoconfig.service` within
seconds, but on first boot the operator sees the raw text frame on
HDMI before splash takes over. There is also a sub-second window
during F10 sessions between `openvt -c 2 -s -f -w` and the wizard
process calling `termios.tcsetattr(tty.setraw())`; the `tty_guard
--clear` ExecStartPre minimizes (but does not eliminate) it. No getty
is competing for tty1 / tty2 / tty3 in this image
(`enabled=disabled`).

### Not observed

- `process_crash`, `apply_policy_missing`, `stdin_tty_lost`,
  `getty_visible`, `kernel_console_visible`, or `vt_not_cleared`
  outside the firstboot-gate window.

## Hotfix applied (P4 — minimal, reversible)

Patch in `scripts/board/totem_open_settings_session.sh`:

```diff
+  set -- $(process_counts)
+  if [ "${1:-0}" -ne 0 ] || [ "${2:-0}" -ne 0 ] || [ "${3:-0}" -ne 0 ] || [ "${4:-0}" -ne 0 ]; then
+    systemctl kill --signal=SIGKILL kiosky-player.service >/dev/null 2>&1 || true
+    pkill -KILL -f '/opt/totem/kiosky-player/kiosk\.py'        >/dev/null 2>&1 || true
+    pkill -KILL -f '/data/apps/kiosky-player/.*/kiosk\.py'     >/dev/null 2>&1 || true
+    pkill -KILL -x mpv                                          >/dev/null 2>&1 || true
+    pkill -KILL -f '/opt/totem/bin/kiosky_service_launcher\.sh'>/dev/null 2>&1 || true
+    pkill -KILL -f '/opt/totem/bin/totem-kiosky-launcher\.sh'  >/dev/null 2>&1 || true
+    for _ in $(seq 1 5); do
+      set -- $(process_counts)
+      if [ "${1:-0}" -eq 0 ] && [ "${2:-0}" -eq 0 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ]; then
+        break
+      fi
+      sleep 1
+    done
+  fi
```

Properties of the patch:

- Preserves the original 30 s SIGTERM grace period.
- Only escalates to SIGKILL when the grace period fails.
- Kills both the legacy path (`/opt/totem/kiosky-player/kiosk.py`) and
  the C14.1.1 pull-update path
  (`/data/apps/kiosky-player/<version>/kiosk.py`).
- Preserves the final `exit 42` guard as a last resort.
- No new dependencies; uses tools already present (`systemctl`,
  `pkill`).
- Reversible: any rebuild from `HEAD~1` of this branch restores prior
  behaviour.

### Hotfix v2 — diagnostic instrumentation (2026-05-13)

After an on-device test #1 failed with `Main process exited,
code=killed, status=15/TERM` without revealing the SIGTERM source in
journalctl, a second small patch was applied to
`scripts/board/totem_open_settings_session.sh`:

- `c15_trace()` helper appending one-line per-phase records to
  `/tmp/c15-session.trace` (best-effort; ignores errors).
- Separate `on_term` / `on_int` / `on_hup` traps that record which
  signal arrived before delegating to the original `on_exit` cleanup.
- Trace points at every major phase: getty stop, show_transition
  before/after, systemctl stop kiosky, drain wait, SIGKILL escalation
  (if entered), openvt start/exit, wizard rc.
- No behaviour change. Pure observability. Reversible by removing the
  `c15_trace` lines.

The instrumented session.sh is sha256
`8484338d9d5a9abbab7ab6e80ad92d1a00dff83d938908edfda04c1cbf93d3f8`.
On-device test #2 with this instrumentation passed end-to-end and
produced the trace file referenced in the evidence README.

### Deployment to lab board (no reboot)

Used the new SSH ControlMaster helper
`scripts/remote/apply_c15_1_1_session_hotfix.sh`. The session.sh on the
board lives under `/opt/totem/bin/`, in the read-only rootfs's tmpfs
overlay. SHA256 before: `ed2a48114edeca47…`. SHA256 after:
`c4cb256cbd023f99…` (matches local). `bash -n` on the board: ok.
`systemctl is-active` for both `totem-settings-trigger.service` and
`kiosky-player.service`: active. The patch is non-persistent across
reboot — the image needs to be rebuilt to bake the fix in (see
"Image rebuild required" below).

## Player audit (P6 — no code change)

Captured from the lab board without printing secrets:

- Current installed version:
  `/data/apps/kiosky-player/current → releases/homolog-20260511-202109-c71318a`
  with `source=github:dadoohai/kiosky-player:totem-app-homolog-20260511-202109-c71318a`,
  applied at `2026-05-12T14:17:36Z`, SHA256
  `0e4c3bbd5a90fcb8dda3672149da9f1dca26e447a67bc32e311d76f6ec83aa5f`.
- MPV process (PID 8927) flags include `--loop-file=inf
  --image-display-duration=inf --keep-open=yes --vo=gpu
  --gpu-context=drm --ao=null --no-input-default-bindings`.
- `kiosk.py` defaults (read from local repo,
  `/home/builder/kiosky-player/kiosk.py`):
  - `default_duration_ms = 10000`
  - `sync_enabled = True`
  - `sync_prep_mode = "play_then_resync"`
  - `sync_hard_resync_ms = 1200`
  - `preload_next = True`
- `/tmp/kiosky-status.json`: `playback_state=playing current_index=5`.

### Hypotheses for the looping / duration / sync symptoms

- `default_duration_used`: when the API returns `exposure_time_ms=0` or
  the field is missing, `kiosk.py` falls back to `default_duration_ms=10000`.
  Because mpv is run with `--loop-file=inf`, a short video (e.g. 3 s)
  will visibly loop ~3× before kiosk's scheduler sends the next
  `loadfile`.
- `sync_resync_conflict`: with `sync_enabled=true` the play loop holds
  the current item past its declared duration when the next UTC
  checkpoint is not ready (anchor missing, drift > hard threshold).
- `mpv_ipc_loadfile_failure`: `kiosk.py` has retry-then-restart logic
  around `mpv.load_file` (line ~2835 onward) for the
  `media_load_failed` case; while the retry is in flight, mpv keeps
  looping the previous media. The MPV diagnostics introduced in
  `kiosky-player` commits `affcdd2` (MPV diagnostics), `7a5f75c`
  (preserve MPV logs by generation) and `52836f3` (configurable ping
  threshold) explicitly track this failure mode.

These are stated as **suspects**, not confirmed root causes. The next
round (`C16.1.1`) should pull `mpv_log_file` traces with
`mpv_debug_events=true`, run the player against a synthetic playlist
with a known short clip, and verify whether disabling `sync_enabled`
for homologation removes the symptom.

### What was NOT done

- No change to `kiosk.py`.
- No change to `/data/config/config.json` (operator-controlled, no
  approval to flip `sync_enabled`).
- No new MPV flag.

## Image rebuild required

The hotfix lives in a tmpfs overlay layer on the lab board. To
persist:

1. Commit the modified `scripts/board/totem_open_settings_session.sh`.
2. Re-run the C14.2.1 build wrapper (`run_c14_2_1_build_shipping_homolog_image.sh`)
   with the same private inputs to mint a new image bundle. The next
   shipping bundle will inherit the SIGKILL escalation and the
   diagnostic trace.

The image rebuild belongs to a follow-up card (`C15.1.3` or a wider
`C15.x` shipping refresh) and is only worth running **after** the
validation battery in `C15.1.2` confirms the wizard is reliable.

## Next card before any image rebuild

`C15.1.2 — wizard reliability battery on lab board`:

- Five consecutive F10 holds in a single uptime window with mixed
  intervals (0 s, 30 s, 1 min, 5 min, 10 min).
- Each test captures `/tmp/c15-session.trace` + `journalctl -u
  totem-open-settings.service` + the screens list + the
  session-status.
- Closure criterion: 5/5 with `code=exited` and no new
  `trap_signal=...` entries. Any failure must be attributable to a
  specific phase via the trace.
- C15.1.2 must be closed before C16.1.1 (player) is opened — the
  themes are distinct (C15 = wizard/firstboot/visual; C16 = player
  scheduler/sync). Rigour over speed.

### C15.1.2 result (2026-05-13)

C15.1.2 executed the five physical F10 attempts on the already-running board.
The warm-runtime wizard flow passed 5/5 by trace (`openvt_exited`,
`WIZARD_RC=8`, writer passed, lock cleaned, player restored), and the C15.1.1
SIGTERM did not recur.

However C15.1.2 is **blocked**, not passed: the operator confirmed that F10
still echoes keyboard characters over the SVG before the screen refresh clears
them. The failure is classified as `keyboard_echo_persisted`, with
`unclassified_failures=0`.

The operator also clarified that the earlier self-exit/login/config_missing
symptoms are most often perceived immediately after power-on. C15.1.2 did not
reboot or power-cycle by restriction, so that cold-boot/first-attempt context is
recorded as not tested, not as passed.

The firstboot gate raw `/dev/tty2` output was removed in
`scripts/board/totem_firstboot_gate.sh` and hotfixed onto the board, but it was
not cold-boot validated because this round did not reboot or power-cycle.

Decision: C15.1.1 remains partial-validated; C15.1.3/C14.2.2 image rebuild is
not released; C16/player remains blocked until C15.1.2 passes.

## What stays untouched

- `C14.2.1` shipping homologation image still flashable; nothing about
  the manifest or the embedded systemd units changed.
- `C14.1.1` pull-update pipeline (timer + service + updater) is
  unchanged. `totem-update-agent.timer` is still `active enabled` with
  `OnBootSec=10min`, `OnUnitActiveSec=6h`, `RandomizedDelaySec=10min`,
  `Persistent=true`.
- `C13.1.3` homologation private seed at
  `/data/state/totem-settings/private-values.seed.json`, mode `0600`,
  parent `0700`, contents not read.
- `C12` read-only and `C12.4` corte seco stay blocked.

## Operator acceptance criteria (P9)

1. F10 opens the wizard on the first attempt OR the failure is
   classified.
2. The wizard does not return to `config_missing` on its own during a
   60 s observation window OR the failure is classified.
3. Terminal/login is not visible OR the cause is classified.
4. No keyboard echo on screen OR the cause is classified.
5. Session lock exists during the wizard and cleans up after.
6. The player / `config_missing` splash does not steal the screen
   while the wizard is active.
7. Player evidence collected without secrets.
8. An initial diagnosis of the duration / looping / sync triad has
   been produced.
9. No big player change without explicit approval.
10. No `apt` / `pip` / `upgrade`.
11. No `poweroff` / power-cut.
12. No secrets published.

## Evidence

`docs/evidence/candidate-a/runs/20260512T151804Z-c15-1-1-wizard-firstboot-player-audit/`

## Theme discipline

C15.x cards belong to **wizard / firstboot / visual session** concerns.
C16.x will belong to **player scheduler / sync** concerns. The player
audit performed here produced suspects only; it does not authorise any
C16 work. C16.1.1 is the recommended **future** card, but it must wait
until C15.1.2 closes the wizard side cleanly.
