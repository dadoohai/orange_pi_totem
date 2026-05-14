# 157 - C16.1 - Prioritized UX/Product Backlog

## Decision Summary

```text
p0_items_count=0
p1_items_count=5
p2_items_count=5
p3_items_count=2
ready_for_c17_image=true
need_c16_2_before_c17=false
blocked_p0_user_journey=false
c16_2_p1_gates_created=true
```

No P0 user-journey blocker was found. C17 can start as the next consolidated
image round, provided C17 validation uses the C16.1 journeys, screen intent map
and rubric. C16.2 is recommended as a useful next methodology increment, but
not mandatory before C17.

## P0 Before C17

None identified in C16.1.

## P1 Preferably Before or During C17 Validation

1. **Negative API/cache/content scenarios.**
   Validate `waiting_for_api`, `waiting_for_media`, `loading_content` and
   `error_no_content` without exposing config or media URLs.

2. **Negative Wi-Fi setup scenarios.**
   Test wrong password and weak/unstable Wi-Fi feedback with sanitized
   evidence.

3. **Update UX path.**
   Review checking/applying/failed update perception. Engineering exists from
   C14, but visual/product states need a journey test.

4. **HDMI/camera perception methodology.**
   SSH/timeline is not enough for flicker, black frames and orientation. This
   is optional before one C17 validation, but required before scale.

5. **Wizard visual consistency pass.**
   Use offline gallery and rubric to raise critical wizard screens to score 4
   or document accepted score 3 tradeoffs.

## P2 Post-C17

1. Wizard layout and visual polish.
2. Shared visual language for wait/error states.
3. Support runbook UI and status observer polish.
4. Offline/cache/no-cache scenario matrix.
5. C18 player timing/sync/looping audit as its own front.

## P3 Aspirational

1. Appliance design system: typography, spacing, colors, visual tokens and
   state components.
2. Motion design and microinteractions after DRM/MPV behavior is fully stable.

## Suggested Fronts

- **C16.2 offline visual QA harness:** gallery diffs, rubric thresholds and
  synthetic user review per persona.
- **C16.3 runtime UX probe:** scenario-oriented sanitized timeline runner.
- **C16.4 targeted P1 fixes:** only if C17 validation finds a blocking
  perception gap.
- **C16.5 HDMI/camera methodology:** capture setup, checklist and thresholds.
- **C17 image build:** consolidate C15.3.2 and C16.1 docs/harness policy.
- **C18 player timing/sync:** return to scheduler, duration, sync and loop when
  the product/UX system is in place.

## C16.2 Update

C16.2 converted the five P1 items above into explicit gates:

- API/cache/content negatives: mandatory C17 gate.
- Wi-Fi wrong password/weak Wi-Fi: mandatory C17 gate.
- Update UX path: mandatory C17 gate with simulation only.
- HDMI/camera methodology: optional before C17, required before scale.
- Wizard visual consistency: mandatory C17 gallery/rubric gate.

C16.2 found no P0 and no critical screen below 4. C17 remains recommended as
the next image round; C16.3 runtime probes and C16.4 visual fixes are not
mandatory before C17.
