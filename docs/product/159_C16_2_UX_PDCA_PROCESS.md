# 159 - C16.2 - UX PDCA Process

## Status

```text
c16_2_ux_pdca_process_created=true
manual_interaction_required=false
runtime_changed=false
board_accessed_via_ssh=false
```

C16.2 uses PDCA as the operating loop for product/UX QA. The goal is to keep
each review small, reproducible and tied to a journey, persona, screen and
rubric score.

## Plan

For each UX QA cycle, define:

- journey under review;
- persona or synthetic user;
- screen or transition;
- hypothesis of the user problem;
- rubric dimension and metric;
- guardrails that must remain unchanged.

## Do

Execute the smallest allowed validation:

- generate or reuse the synthetic gallery;
- run the synthetic-user review;
- run an offline fixture or synthetic status scenario;
- run a runtime probe only when a specific card authorizes it;
- apply a small product/UI change only if that card explicitly authorizes code
  changes.

## Check

Compare the result against the planned metric:

- compare journey and screen scores;
- verify guardrails;
- verify public-safe status;
- if runtime is involved, collect a sanitized timeline;
- if perception is involved, collect HDMI/camera evidence when available.

## Act

Choose one outcome:

- accept the state;
- open a focused fix;
- defer to a later product round;
- block the image;
- create a C17, scale or C18 gate.

## Blocking Rule

- P0 always blocks the image.
- P1 blocks the image only if it is in a critical journey and there is no
  reliable validation gate.
- P2 and P3 do not block the image.

## Guardrails

UX PDCA must not alter appliance runtime, real network state, real config,
writer behavior, package state, kernel/read-only work, player timing, sync,
duration or loop semantics unless a later card explicitly authorizes that
specific scope.
