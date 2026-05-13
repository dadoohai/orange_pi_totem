# C15.1.1 — Wizard/firstboot/F10 stabilization + player timing audit

Run identifier: `20260512T151804Z-c15-1-1-wizard-firstboot-player-audit`
Card status: hotfix-deployed-and-instrumented; 1-of-2 on-device tests
passed; first-test root cause **still unclassified**; closure pending a
deliberate validation battery (recommended next: `C15.1.2`)
Operator role: audit + minimal hotfix + diagnostic instrumentation +
on-device validation

## Identity

- card: `c15.1.1`
- title: First boot / F10 wizard stabilization and player timing audit
- branch: `foundation-v0.1`
- previous_card: `c14.2.1`
- next_recommended_card: `c16.1.1` (player scheduler audit — sync_resync vs api duration)

## Boundaries

- `board_accessed_via_ssh=true`
- `secrets_published=false`
- `apt_update_executed=false`
- `apt_upgrade_executed=false`
- `pip_install_executed=false`
- `poweroff_executed=false`
- `power_cut_tested=false`
- `read_only_touched=false` (overlayroot=tmpfs intact)
- `kernel_touched=false`
- `uboot_touched=false`
- `dtb_touched=false`
- `bsp_touched=false`
- `wifi_touched=false`
- `networkmanager_touched=false`
- `seed_content_read=false`
- `config_json_content_read=false` (only non-sensitive scalar fields enumerated)
- `mender_rauc_swupdate_used=false`
- `c12_readonly_blocked=true`
- `c12_4_blocked=true`
- `password_persisted=false`
- `ip_published=false`
- `mac_published=false`

## Image identity (sanitized)

- image: `c14-2-1-shipping-homolog` (running on lab board)
- kernel: `6.12.58-current-sunxi64`
- lab_firstboot_mode: `private_disposable_lab`
- homologation_seed_enabled: `true`
- artifact_private: `true`
- final_image: `false`
- not_for_production: `true`
- not_for_distribution: `true`

## Baseline runtime snapshot (before hotfix)

Captured via `scripts/remote/inspect_c15_1_1_runtime.sh`
(sanitized; no IPs/MACs/secrets/config.json contents).

- uptime: `1:14, load 1.30 1.59 1.76`
- fgconsole: `2` (visual VT)
- kiosky-player.service: `active enabled` — pid 5757 (launcher) → 5803 (kiosk.py) → 8927 (mpv)
- totem-update-agent.timer: `active enabled`
- totem-settings-trigger.service: `active enabled`
- totem-open-settings.service: `inactive static` (oneshot, fires on F10)
- totem-firstboot-gate.service: `inactive enabled` (firstboot done)
- dadooh-visual-splash.service: `inactive enabled`
- getty@tty1/2/3: `inactive disabled` — no getty competing
- getty@tty0: `inactive disabled`
- serial-getty@ttyS0: `active enabled` (serial only, not on HDMI)
- console-setup.service: `failed` (font/keymap; cosmetic, no impact on HDMI rendering)
- /proc/cmdline (sanitized): `... splash=verbose console=ttyS0,115200 consoleblank=0 loglevel=0 quiet systemd.show_status=false rd.systemd.show_status=false logo.nologo vt.global_cursor_default=0 overlayroot=tmpfs cgroup_enable=memory ...`
- session_lock_dir_exists: `false`
- trigger-status: `status=timeout trigger_detected=False session_lock_active=False stale_lock_suspected=False cooldown_active=False raw_key_values_logged=False characters_logged=False`
- last open-settings failure: `1 incident at 2026-05-12T11:04:04Z` (then recovered; config.json now populated with 33 keys)
- /data/apps/kiosky-player/current: `releases/homolog-20260511-202109-c71318a`
- updatectl status: `service_active=true current_payload_sha256=0e4c3bbd5a... previous=homolog-20260511-202109-c71318a` (single applied version)

## wizard_before (observed symptoms)

- `config_missing_returned`: `true` (operator reports first/second F10 attempt sometimes drops back to config_missing/player splash; third attempt succeeds)
- `tty_login_visible`: `partial` (briefly during first boot; no getty competing thereafter, but firstboot gate prints raw text to /dev/tty2)
- `keyboard_echo_visible`: `partial` (intermittent, narrow window during wizard handoff)
- `session_lock_present`: `false` (cleans up on service stop)

### Wizard pipeline (mapped)

1. `totem-settings-trigger.service` daemon reads `/dev/input/event*` via evdev (no character logging) and detects F10 hold ≥ 5s.
2. Trigger calls `systemctl start totem-open-settings.service` (one-shot).
3. `totem-open-settings.service` ExecStartPre:
   - `totem_visual_tty_guard.sh --clear --tty 2` (clears screen, disables echo, hides cursor on tty2)
   - `totem_settings_lab_apply_policy.sh --enable-from-homologation-seed-if-present` (writes `/run/dadooh-settings/apply-policy.json` with `mode=real-write homologation_seed=true` when seed is enabled)
4. `totem-open-settings.service` ExecStart: `totem_open_settings_session.sh` which:
   - creates lock dir `/run/totem/settings-session.lock` (exits 23 if already held)
   - stops `getty@tty1.service` and `getty@tty2.service` (idempotent — already disabled in this image)
   - `show_transition setup` (clear+splash render on /dev/tty2)
   - stops `kiosky-player.service` and waits up to 30s for `kiosk.py`+`mpv`+renderer+setup processes to drain
   - **if not drained: `exit 42 hdmi_not_free_after_player_pause`** ← root-cause of "wizard came back" before C15.1.1
   - runs wizard via `setsid openvt -c 2 -s -f -w -- python3 totem_setup_visual_wizard.py`
   - waits up to `--timeout-sec 7200`
   - on exit/cancel: `restore_service` shows transition then `systemctl start kiosky-player.service`
   - cleans lock and trigger request

## Root-cause classification

- `wizard_exit_cause=service_race_with_config_missing`
  - **Specific:** `hdmi_not_free_after_player_pause` (exit 42) on first/second attempts when player launcher's bash subprocesses do not propagate SIGTERM cleanly within the 30 s grace period. Subsequent attempts succeed because residual processes have fully drained.
- `tty_leak_cause=renderer_starts_too_late`
  - **Specific:** `totem_firstboot_gate.sh` prints raw text to `/dev/tty2` (line 114–122 of `scripts/board/totem_firstboot_gate.sh`) before the splash python takes over on first boot. Plus narrow window (<300 ms) after `openvt` switch and before `tty.setraw` inside the wizard during F10 sessions (mitigated by `tty_guard --clear` ExecStartPre).
- No `process_crash`, `apply_policy_missing`, or `stdin_tty_lost` detected in evidence.

## Hotfix applied (P4 — minimal correction)

Patch: `scripts/board/totem_open_settings_session.sh` — replace bare `exit 42` with SIGKILL escalation.

Diff (semantic):

```
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

The remaining `exit 42` is preserved as final guard for truly stuck systems.

### Deployment to lab board (overlayroot=tmpfs, no reboot)

- target: `/opt/totem/bin/totem_open_settings_session.sh`
- baseline sha256: `ed2a48114edeca47464ae2d6b421bbbc0badc753208ab6b98ee97976686edd6a`
- new sha256:      `c4cb256cbd023f99aee1e85b11dcd07c2eba8e28a25174d78cfc85577b2619e3` (matches local)
- bash -n on board: ok
- trigger active: yes
- player active: yes
- no service restart needed (script is re-read on each open-settings activation)
- persistence: lives in tmpfs upper layer; reverts on reboot → image rebuild required for permanence (see "ready_for_image_rebuild" below)

## wizard_after (physical test, P5)

Two operator-driven F10 tests were run on the lab board after the C15.1.1
hotfix was deployed.

### Test #1 — 2026-05-13T10:03:47Z (failed; cause indeterminate)

- F10 hold detected, `totem-open-settings.service` started.
- Player stopped cleanly in 2 s (10:03:49Z) — SIGKILL escalation **not**
  needed.
- Wizard rendered `01-orientation` and `01-orientation-confirm`.
- At 10:03:55Z (~8 s after service start) `session.sh` was killed by
  SIGTERM (`Main process exited, code=killed, status=15/TERM`).
- Operator-reported symptom: wizard exited when navigating from
  "manter wifi" toward the environment step.
- Diagnostic instrumentation was not yet active during this run, so
  the SIGTERM source could not be attributed to a specific subsystem.
  Candidates considered: external `systemctl stop`, OOM (kernel
  SIGKILL, ruled out — signal was 15 not 9), `kiosky-player`
  Restart=always cascade (ruled out — explicit stop), trigger
  daemon's `subprocess.run timeout=5` killing systemctl client
  (ruled out — disconnecting the D-Bus client does not cancel a job
  already in execution).
- Outcome: operator saw the splash return to media. No data loss; no
  reboot; player resumed playback.

After this run a **hotfix v2** instrumentation was deployed
(`scripts/board/totem_open_settings_session.sh` sha256
`8484338d9d5a9abbab7ab6e80ad92d1a00dff83d938908edfda04c1cbf93d3f8`):

- `c15_trace()` helper writing per-phase timestamps to
  `/tmp/c15-session.trace`.
- Separate `on_term` / `on_int` / `on_hup` traps that log which signal
  arrived before delegating to the existing `on_exit` cleanup.
- No behaviour change; pure observability.

### Test #2 — 2026-05-13T10:25:38Z–10:26:07Z (success, full cycle)

Trace excerpt (sanitized):

```
13:25:39.115 session_sh_start          ppid=1
13:25:39.435 before_getty_stop
13:25:39.564 before_show_transition_1
13:25:40.142 after_show_transition_1   INITIAL_SERVICE_ACTIVE=active
13:25:40.546 after_systemctl_stop_kiosky
13:25:40.709 after_drain_wait          counts=0,0,0,0 (clean drain in ~160 ms)
13:25:40.868 before_show_transition_2
13:25:41.437 after_show_transition_2
13:25:41.596 before_openvt
13:25:41.601 openvt_started            pid=56910
13:25:49.647 openvt_exited             WIZARD_RC=8 (operator confirmed all 6 screens)
13:25:49.656 after_wizard              WIZARD_RC=8
2026-05-13T10:26:07 totem-open-settings.service: Deactivated successfully
```

Screens written:
`0001-01-orientation.svg`, `0002-01-orientation-confirm.svg`,
`0003-02-connection.svg`, `0004-03-environment.svg`,
`0005-05-review.svg`, `0006-06-complete.svg`.

`session-status.json` (sanitized highlights):

- `apply_mode=real-write`
- `homologation_seed_mode=True`
- `policy_used=True policy_private_source=homologation-seed`
- `writer_called=True writer_rc=0 writer_result=passed`
- `handoff_rc=0 private_candidate_real_dry_run_passed=True`
- `real_config_written=True backup_created=True`
- `private_candidate_removed=True apply_policy_removed=True`
- `service_restore_attempted=True service_active=active service_enabled=enabled`
- `setup_cancelled=False`
- `linux_prompt_visible=False`
- `network_step=existing_configured_wifi` (operator chose "manter wifi")
- `selected_rotation_deg=270 orientation_category=portrait_left`
- `nrestarts=0`
- `power_cut_tested=False networkmanager_changed=False root_read_only_enabled=False`

Backup file written by writer (no content read):
`/data/config/backups/config.json.20260513T132551Z.56939.bak` (1514 bytes,
root:totem 0600).

`/data/state/totem-settings/last-settings.json` updated at
2026-05-13 10:25:51 (305 bytes, 0600).

Acceptance flags after test #2:

- `wizard_f10_opens_first_try=true`
- `wizard_stays_open_60s=true` (wizard ran to completion in ~29 s with operator
  confirming six screens; never returned to player splash during the run)
- `config_missing_returns_during_wizard=false`
- `tty_login_visible=false` (`linux_prompt_visible=False` in status)
- `keyboard_echo_visible=false` (no operator report of echo this round)
- `session_lock_cleans_up=true` (`/run/totem/settings-session.lock` absent
  post-test; `open-settings-cleanup-status.json` recorded
  `reason=service-stop-post`)

### Reproduction summary

| Run | Outcome | Signal | Wizard runtime | Screens written | Real-write |
|-----|---------|--------|----------------|-----------------|------------|
| 10:03:47Z | failed | SIGTERM (15) from indeterminate source | ~8 s | 2 (orientation*) | no |
| 10:25:38Z | success | none | ~29 s end-to-end | 6 (full cycle) | **yes** |

The instrumentation is now in place. Any future failure will leave a
`/tmp/c15-session.trace` line indicating which signal landed, when, and
which phase `session.sh` had reached — so a repeat will be classifiable
without guesswork.

## player_audit (P6, no big change)

- `current_app_source=data` (`/data/apps/kiosky-player/current → releases/homolog-20260511-202109-c71318a`)
- `app_version=homolog-20260511-202109-c71318a`
- `app_source=github:dadoohai/kiosky-player`
- `mpv_process_present=true` (pid 8927)
- `mpv_flags`: `--loop-file=inf --image-display-duration=inf --keep-open=yes --no-osc --osd-level=0 --vo=gpu --gpu-context=drm --ao=null --no-input-default-bindings --video-rotate=270`
- `kiosk_default_duration_ms=10000` (kiosk.py hardcoded default — applies when API `exposure_time_ms` is 0/missing)
- `kiosk_sync_enabled_default=true` (kiosk.py default)
- `kiosk_sync_prep_mode=play_then_resync`
- `kiosk_sync_hard_resync_ms=1200`
- `kiosk_preload_next_default=true`
- `status_file_present=true` → `/tmp/kiosky-status.json` reports `playback_state=playing current_index=5`
- `playback_state=playing`
- `loop_active_observed=false_in_this_snapshot`

### Player timing suspects

Classified (non-exhaustive, can hold more than one):

- `default_duration_used` — when API `exposure_time_ms` is 0/missing, `kiosk.py` falls back to `default_duration_ms=10000`. For short media (e.g. 3 s video), `mpv --loop-file=inf` loops the file ~3× before kiosk advances → visual perception of "looping".
- `sync_resync_conflict` — `sync_enabled=true` default; `sync_prep_mode=play_then_resync` waits on UTC anchor checkpoints. If the anchor service or the upstream sync source is not consistent in homologation, kiosk's advance loop can hold the current item past its `duration_ms`.
- `mpv_ipc_loadfile_failure` — intermittent IPC retries observed in repo journal (C14.1.1 MPV diagnostics commits `affcdd2`, `7a5f75c`); when retry fails kiosk restarts MPV but, with `loop-file=inf`, the previous media keeps playing until restart completes.

`player_timing_suspect=default_duration_used,sync_resync_conflict,mpv_ipc_loadfile_failure`

`player_code_changed=false` (intentional: P6 audit-only)

### Safe config mitigation considered

- Disabling `sync_enabled` in `/data/config/config.json` would isolate the sync component as a suspect, but altering customer config is out-of-scope for C15.1.1 without operator approval. Recorded as a candidate for C16.1.1.

## File / artifact inventory

- new: `scripts/remote/inspect_c15_1_1_runtime.sh` (SSH ControlMaster runtime inspector, password via env, sanitized output)
- new: `scripts/remote/apply_c15_1_1_session_hotfix.sh` (SSH ControlMaster hotfix deployer, sha256 verification)
- modified: `scripts/board/totem_open_settings_session.sh` (SIGKILL escalation before `exit 42`)
- new: `docs/product/137_C15_1_1_WIZARD_FIRSTBOOT_AND_PLAYER_TIMING_AUDIT.md`
- new: this evidence README
- new: `runtime-audit.out` (sanitized inspect output captured to `.cache/`; mirrored summary below)

## On-board verification commands executed (sanitized excerpts)

The full sanitized capture lives at `.cache/c15-1-1-runtime-audit.out`; selected lines:

```
=== unit state (key services) ===
kiosky-player.service                      active=active     enabled=enabled
totem-update-agent.timer                   active=active     enabled=enabled
totem-update-agent.service                 active=inactive   enabled=static
totem-settings-trigger.service             active=active     enabled=enabled
totem-open-settings.service                active=inactive   enabled=static
totem-firstboot-gate.service               active=inactive   enabled=enabled
dadooh-visual-splash.service               active=inactive   enabled=enabled

=== unit state (getty/serial) ===
getty@tty1.service                         active=inactive   enabled=disabled
getty@tty2.service                         active=inactive   enabled=disabled
getty@tty3.service                         active=inactive   enabled=disabled
serial-getty@ttyS0.service                 active=active     enabled=enabled

=== fgconsole / openvt? ===
fgconsole=2 openvt=present chvt=present setterm=present

=== /run/dadooh-settings/trigger-status.json ===
  status=timeout trigger_detected=False request_written=False
  session_lock_active=False stale_lock_suspected=False cooldown_active=False
  raw_key_values_logged=False characters_logged=False credentials_collected=False

=== /tmp/dadooh-status/status.json ===
  state=player_running schema_version=totem-status.v0

=== /tmp/kiosky-status.json ===
  playback_state=playing current_index=5

=== /data/config/config.json (non-sensitive fields enumerated) ===
  status_file=/tmp/kiosky-status.json
  rotation_deg=270
  config_keys_total=33
  config_keys_redacted=31

=== systemd-coredump or service crashes (counts) ===
May 12 11:04:04 orangepizero3 systemd[1]: Failed to start totem-open-settings.service - Dadooh Open Totem Settings.

=== current foreground VT ===
fgconsole_now=2
```

## Acceptance status (P9, current)

| # | Criterion | Status |
|---|---|---|
| 1 | F10 opens wizard on 1st try OR classified | **partial** — test #2 opened first try; test #1 failed before any wizard screen, classified only as `SIGTERM from indeterminate source`. Not enough data to claim "passed". |
| 2 | Wizard stays open 60 s OR classified | **partial** — test #2 ran end-to-end (~29 s) without falling back; test #1 fell at ~8 s with cause unidentified. |
| 3 | No terminal/login visible OR classified | **passed** — `linux_prompt_visible=False` in test #2 session-status; firstboot-gate path classified for first boot only. |
| 4 | No keyboard echo OR classified | **passed** — no echo reported in test #2; mitigations from `tty_guard --clear` + `tty.setraw` confirmed in the trace. |
| 5 | Session lock exists + cleans up | **passed** — `/run/totem/settings-session.lock` was held during wizard, removed by ExecStopPost; verified absent post-test in both runs. |
| 6 | Player/config_missing does not steal screen while wizard active | **partial** — SIGKILL escalation hotfix is in place but was **not exercised** in either test (player drained in 2 s both times). The hotfix is a safety net, not a confirmed fix for the observed symptom. |
| 7 | Player evidence collected without secrets | **passed** |
| 8 | Initial diagnosis of duration/looping/sync produced | **passed** — three suspects categorised: `default_duration_used`, `sync_resync_conflict`, `mpv_ipc_loadfile_failure`. No code change. |
| 9 | No big player change without approval | **passed** — `player_code_changed=false`. |
| 10 | No apt/pip/upgrade | **passed** |
| 11 | No poweroff/power-cut | **passed** |
| 12 | No secrets published | **passed** — repo + evidence scanned; SSH password never written; IPs sanitised. |

### Closure call (honest)

Three of twelve criteria are still **partial**, not "passed". This card
should **not** be marked closed until a validation battery on the lab
board completes without unclassified failures. Recommended sequel
card: `C15.1.2 — wizard reliability battery` — five consecutive F10
holds in a single uptime window with mixed inter-test intervals, each
captured by the trace + journal helpers introduced here. Closure
criteria for `C15.1.2`: 5/5 with `code=exited` (no `code=killed`) and
no new `signal=` traps; or any failure classified to a specific phase
via `/tmp/c15-session.trace`.

## Follow-ups

- `ready_for_c16_player_fix=true` — recommended next card: investigate API `exposure_time_ms` actual values + sync scheduler behaviour in homologation; consider operator-approved `sync_enabled=false` mitigation; add MPV `loadfile` telemetry to status writer.
- `ready_for_image_rebuild=true` — once on-board test passes, the same hotfix should be baked into a C14.2.2 / C15.1.2 image so that any reboot keeps the fix (current image: tmpfs-only).
- recorded but **not** done in this round:
  - GPG signing of update manifests (C14 hardening)
  - per-card flash dispatch (waits for batch flow)

## Roadmap pointer

- Updated `docs/product/02_ROADMAP_IMPLEMENTACAO_PRODUTO.md` with a single-line C15.1.1 entry.
- Image-lab manifest (`releases/image-lab-readonly/manifest.md`) is unchanged for this card (no new image yet).
