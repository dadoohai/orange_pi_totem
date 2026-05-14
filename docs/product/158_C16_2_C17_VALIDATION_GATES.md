# 158 - C16.2 - C17 Validation Gates

## Status

```text
c16_2_status=passed
c17_validation_gates_created=true
ready_for_c17_image=true
need_c16_3_runtime_probes_before_c17=false
need_c16_4_visual_fix_before_c17=false
blocked_p0_user_journey=false
```

C16.2 converted the inherited C16.1 P1 items into executable C17, scale and
C18 gates. No P0 was found. C16.3 runtime probes are useful but not mandatory
before starting C17 because each remaining P1 has a concrete validation gate.

## Mandatory C17 Gates

### C17-GATE-BOOT-CONFIG

Boot, config pending/config missing and first setup must show public feedback
and must not expose a terminal, raw technical screen or black wait.

### C17-GATE-WIFI-NEGATIVE

Wrong password and weak Wi-Fi must produce recoverable, sanitized feedback.
C16.2 can simulate list/error states offline; C17 should validate the runtime
path when a board validation card allows it.

### C17-GATE-API-CACHE-CONTENT

API unavailable, media unavailable, no internet and no cache must not become
black-screen waits. The gate must cover `loading_content`, `waiting_for_api`,
`waiting_for_media` and `error_no_content`.

### C17-GATE-UPDATE-UX

Update checking, applying and failed states must be simulated without applying a
real release. A failed update must communicate that the previous working state
is preserved.

### C17-GATE-WIZARD-VISUAL-CONSISTENCY

Critical wizard screens must score at least 4 in the gallery/rubric pass or
document an accepted tradeoff. C16.2 scored the critical set without any screen
below 4, so C16.4 is not required before C17.

## Optional Before C17

- HDMI/camera capture is optional for starting one C17 image pass, provided the
  limitation is recorded.
- C16.3 runtime probes are optional before C17 because the P1 items are now
  explicit C17 gates.

## Required Before Scale

- HDMI/camera methodology for flicker, black frames, orientation and transition
  perception.
- Runtime public-status evidence that separates network, API, cache, media,
  update and player categories.
- Repeated C17 gate pass on the intended image flow.

## C18 Gates

Player timing, sync, duration, playlist cadence and loop semantics remain
outside C16.2/C17. They belong to C18 or later.

## Remote-Update Testable Gates

- Wi-Fi visual copy and synthesized nmcli-output scenarios.
- API/cache/content public status copy and state classification.
- Update UX simulated states.
- Wizard visual copy/layout refinements that do not change runtime contracts.

## Inherited P1 Conversion

### Negative API/cache/content scenarios

- Decision: C17 gate.
- Can simulate offline: true.
- Needs C16.3 before C17: false.
- Needs C18: false, except for later timing/sync/duration/loop work.

### Wi-Fi wrong password / weak Wi-Fi

- Decision: C17 gate.
- Needs board for final runtime confidence: true.
- Can simulate nmcli output: true.
- Requires physical interaction in C16.2: false.

### Update UX path

- Decision: C17 gate.
- Can simulate without applying release: true.
- Needs status update screen/path: true.

### HDMI/camera methodology

- Decision: optional before C17, mandatory before scale.
- Mandatory before C17: false.
- Mandatory before scale: true.

### Wizard visual consistency

- Decision: C17 gate by gallery/rubric.
- Can be evaluated offline: true.
- Screens below 4 in C16.2 critical set: false.
- Needs C16.3/C16.4 before C17: false.
