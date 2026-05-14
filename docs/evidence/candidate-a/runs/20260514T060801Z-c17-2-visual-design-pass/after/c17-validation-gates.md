# C16.2 C17 Validation Gates

## Mandatory C17 Gates

- C17-GATE-BOOT-CONFIG: boot, config_pending/config_missing and first setup
  must show public feedback and no technical screen.
- C17-GATE-WIFI-NEGATIVE: wrong password and weak Wi-Fi must produce
  recoverable, sanitized feedback.
- C17-GATE-API-CACHE-CONTENT: API unavailable, media unavailable, no
  internet and no cache must not become black-screen waits.
- C17-GATE-UPDATE-UX: update checking/applying/failed states must be
  simulated without applying a real release.
- C17-GATE-WIZARD-VISUAL-CONSISTENCY: gallery/rubric minimum score is 4
  for critical wizard screens.

## Optional Before C17

- HDMI/camera capture is optional for starting one C17 image pass, provided
  C17 records the limitation and keeps the scale gate open.
- C16.3 runtime probes are optional before C17 because each inherited P1 now
  has a specific C17 gate.

## Required Before Scale

- HDMI/camera methodology for flicker, black frames, orientation and
  transition perception.
- Runtime status evidence that separates network, API, cache, media, update
  and player categories.

## C18 Gates

- Player timing, sync, duration, playlist cadence and loop semantics remain
  outside C16.2/C17 and belong to C18 or later.

## Remote-Update Testable Gates

- Wi-Fi visual copy and synthesized nmcli-output scenarios.
- API/cache/content public status copy and state classification.
- Update UX simulated states.
- Wizard visual copy/layout refinements that do not change runtime contracts.

## Screen Threshold Result

- critical_screens_below_4=false
- screens_scored_count=25
- journeys_scored_count=15
