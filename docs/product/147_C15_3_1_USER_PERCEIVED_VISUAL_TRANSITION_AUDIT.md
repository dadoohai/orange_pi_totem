# 147 - C15.3.1 - User-perceived visual transition audit

## Status

```text
c15_3_1_status=passed
decision=passed_with_p1_feedback_gap
manual_interaction_required=false
operator_keypress_required=false
c16_started=false
ready_for_c15_3_2_feedback_fix=true
ready_for_c16_player_audit=false
```

C15.3.1 audits the user-perceived visual journey after C15.2.4, without
opening C16 and without touching player timing, sync, duration, scheduler, or
`kiosk.py`.

C15.2.4 passed clean-board image validation, but the operator observed a
transient black interval after "Iniciando player". SSH, NetworkManager, writer,
session cleanup, player restore, and playback were healthy. This card treats
that as a perceived-feedback gap, not as the C15.2.2 failure mode.

## Journey Map

| Step | Screen/phase | User intention | Current feedback | Risk | Needs change |
| --- | --- | --- | --- | --- | --- |
| A | Power-on / boot inicial | Totem is starting | Boot splash can render "Inicializando" | Early firmware/kernel gap cannot be fully covered | No P0 |
| B | Firstboot gate | Appliance is preparing first use | Firstboot/preparing splash, no raw TTY text | HDMI capture still needed for final perception | No P0 |
| C | Config pending / config_missing | User must press F10 | `config_pending` splash and status renderer | Clear enough after C15.1.3 | No P0 |
| D | F10 detected | User asked to configure | Trigger opens settings session | Depends on TTY/session lock | Covered by C15.2.4 |
| E | Abrindo configuracao | System is switching from player to wizard | `setup` splash | Short handoff gap possible | No P0 |
| F | Wizard orientation/display | Operator chooses orientation | Wizard page | UX can be polished later | P2 |
| G | Wizard connection choice | Operator chooses network path | Wizard page | Copy density was reduced in C15.1.5 | P2 |
| H | Wi-Fi list | Operator selects network | Paginated list, signal percent/bars/bucket, refresh | Functional; visual polish later | P2 |
| I | Wi-Fi password | Operator enters password | Hidden by default, F2/Ctrl+P toggle | Fixed V/v issue in C15.2.2 | No P0 |
| J | Environment | Operator enters environment | Debounced text input | C15.2.2 fixed time-jump timeout | No P0 |
| K | Review | Operator confirms | Review page | Acceptable | P2 |
| L | Salvando configuracao | Writer is applying config | `saving` splash | Covered while writer runs | No P0 |
| M | Iniciando player | Player service is being restored | `player` splash before app start | Splash can disappear before first media frame | P1 |
| N | Espera por midia/cache/API | Player may fetch playlist/cache/media | No explicit public wait state today | User can see black and assume freeze | P1 |
| O | Primeiro frame/midia | First playable frame arrives | MPV/player owns HDMI | Handoff may be abrupt | P1 |
| P | Player normal | Totem is operating | Playback state is `playing` | Healthy in C15.2.4 and C15.3.1 monitor | No P0 |

## Runtime Timeline

A new monitor was added:

```text
scripts/remote/c15_3_1_visual_transition_timeline.sh
```

It writes a sanitized timeline under:

```text
/data/state/totem-debug/c15-3-1/<run-id>/
```

The monitor samples public/safe signals only:

- monotonic uptime and boot id;
- systemd active states for totem/kiosky services;
- splash mode/status file when present;
- public player state and playback state;
- process presence booleans for kiosk/MPV/openvt;
- session lock;
- NetworkManager connected category without SSID/IP/MAC/DNS;
- SSH active boolean;
- last wizard phase from `/tmp/c15-session.trace`, sanitized.

It does not read real config, seed, NetworkManager profiles, SSID, password,
IP, MAC, DNS, or raw logs. It does not call writer, reboot, poweroff, or change
Wi-Fi.

The C15.3.1 runtime monitor was executed with the player already recovered from
the C15.2.4 setup:

```text
monitor_run=/data/state/totem-debug/c15-3-1/20260513T213308Z-pid9978
sample_count=72
timeline_window_sec=178
screen_counts.player_playing=72
playback_state_counts.playing=72
ssh_remained_active=true
network_remained_connected=true
boot_id_changed=false
timeline_black_interval_observed=false
```

It did not reproduce a live black interval. SSH and network remained active,
playback was `playing`, and no boot-id change was observed.

## Status Observability

```text
status_observability=partial
```

Current public signals are enough to know whether the wizard/session/player are
healthy:

- splash status exists;
- launcher status exists;
- aggregated public status exists;
- player playback status exists;
- session trace exists when settings was used.

They are not enough to explain the pre-first-frame wait from the user's
perspective. There is no explicit public status for:

- waiting for playlist/API;
- downloading or validating media cache;
- player ready but first frame not yet presented;
- MPV/DRM handoff stage.

That is the main C15.3.1 gap.

## Black Interval

```text
black_interval_observed=true
black_interval_duration_sec=unknown
black_interval_cause=unknown
feedback_visible_during_wait=false
```

The black interval is known from the C15.2.4 operator report, but it was not
reproduced during this non-interactive SSH-only monitor run. The probable
mechanisms are:

- `waiting_for_media_without_feedback`;
- `media_cache_download_wait`;
- `api_playlist_wait`;
- `splash_to_mpv_handoff_gap`;
- `drm_plane_transition`.

The current evidence does not distinguish those mechanisms. The product risk is
clear even without that distinction: a valid wait can look like a freeze.

## Backlog

### P0

None found in C15.3.1.

No evidence in this card shows a persistent black screen, setup failure, shell
leak, keyboard echo, SSH loss, NetworkManager loss, OOM, panic, reboot, or
player restore failure.

### P1

1. Add an explicit user-facing "Preparando midias" or "Carregando conteudo"
   state between `Iniciando player` and the first confirmed playback frame.
   This can be implemented in C15 core/launcher/status handoff before C16 if it
   avoids changing scheduler/sync/duration.

2. Add public-safe status categories for player startup readiness: waiting for
   API/playlist, waiting for cache/media, and first-frame-ready/playing. This
   likely needs coordination with player status output, but should not change
   playback timing semantics.

3. Keep the player/startup splash visible until a safe readiness condition is
   reached, or replace it with a static waiting screen if MPV has not produced a
   frame yet. This must avoid fighting MPV/DRM once playback owns the display.

### P2

1. HDMI capture or camera-based perception QA for real flicker/black-screen
   duration.

2. Visual design PDCA for the full wizard, using generated galleries plus
   human/vision review.

3. More polished microcopy, spacing, typography, and optional motion/spinner
   once the state model is reliable.

## Decision

C15.3.1 passes as an audit because it produced the journey map, monitor,
observability classification, and prioritized backlog without violating
guardrails.

It does not recommend opening C16 immediately. The next practical step is a
small C15.3.2 feedback fix focused on the pre-first-frame wait and startup
status visibility. C16/player timing/sync/looping should remain unopened until
that perceived-feedback gap is handled or explicitly waived.

Follow-up: C15.3.2 implemented a minimal player startup feedback bridge and
re-enabled C16 audit readiness without starting C16.

## Evidence

`docs/evidence/candidate-a/runs/20260513T212929Z-c15-3-1-user-perceived-visual-transition-audit/`
