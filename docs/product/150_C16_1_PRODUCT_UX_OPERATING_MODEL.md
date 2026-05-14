# 150 - C16.1 - Product/UX Operating Model

## Status

```text
c16_1_status=passed
runtime_changed=false
board_accessed_via_ssh=false
c16_started_as_product_ux_qa=true
c16_player_timing_started=false
c12_readonly_blocked=true
c12_4_blocked=true
ready_for_c17_image=true
need_c16_2_before_c17=false
c16_2_executable_harness_created=true
```

C16.1 changes the operating model for product, UX, visual QA and engineering
decision-making. It does not correct one isolated screen and it does not touch
the appliance runtime. The goal is to make future UX/UI evolution systematic,
testable and compatible with the Orange Pi appliance constraints.

## Experience Objective

The totem must feel like a dedicated product, not like a Linux computer. A
person standing in front of it should always understand:

- what state the device is in;
- whether an action is expected;
- whether the system is working or waiting;
- what can be done when something fails.

The remote support person must also understand the same state from sanitized
public status, without seeing secrets or requiring raw logs.

## Technical Premises

The UX is shaped by hard technical boundaries:

- Armbian/Debian Bookworm Minimal on Orange Pi Zero 3;
- no desktop, no Chromium, no Xorg, no Wayland and no compositor;
- MPV owns video through DRM/KMS;
- systemd controls player, setup trigger, visual guard and updater;
- local setup happens through a framebuffer/SVG wizard;
- remote updates happen through GitHub Releases pull updater;
- `/data` carries config, state and mutable app data;
- read-only/C12 is still blocked;
- planned power-cut/C12.4 is still blocked.

These boundaries are not temporary UI inconveniences. They are product
constraints. UX work must improve clarity without adding heavy dependencies or
weakening the appliance model.

## Design Principles

1. The user always understands the current state.
2. A valid wait must never look like a freeze.
3. A technical terminal, shell, login prompt or raw traceback must never be
   visible to the operator.
4. Every interactive screen has one clear primary action.
5. Secondary actions are explicit and short.
6. Errors are recoverable or clearly escalated to support.
7. The first-run flow must work without training.
8. Secrets never appear in UI, status, docs, evidence or logs.
9. Robustness is more important than visual flourish.
10. No UX improvement may require desktop/browser/compositor infrastructure.
11. No UX improvement may change playback scheduler, sync, duration or loop
    semantics unless a later player-specific card explicitly authorizes it.

## Shared Language

- **State:** what the system is actually doing.
- **Perceived state:** what the user thinks is happening from the screen.
- **Feedback:** visible or public-safe signal that bridges state and perceived
  state.
- **Primary action:** the one action the user is expected to take now.
- **Recovery:** the safe next step after an error.
- **P0:** use-blocking or trust-breaking issue.
- **P1:** important issue in a critical journey, but recoverable.
- **P2:** polish, clarity or consistency improvement.
- **P3:** aspirational product-quality improvement.

## What Good Means

For this appliance, "good experience" means:

- boot/setup/player states are explicit;
- setup can be completed by a non-technical installer;
- waiting for API, cache, media or player startup is visible;
- failures are categorized and recoverable;
- the player looks intentional even before content starts;
- support can diagnose from public status without exposing private data;
- UI changes can be evaluated by repeatable offline and runtime QA.

## C16.1 Decision

C16.1 found no P0 product/UX blocker. Remaining P1 work is accepted as either
C17 validation criteria or follow-up C16.2/C16.3 harness improvements. C17 can
start as the next consolidated image round, but it must use the C16.1 journeys,
screen intent map and rubric as validation gates.

## C16.2 Pointer

C16.2 implemented the executable synthetic-user UX review harness and converted
the inherited P1 items into C17/C18/scale gates. See:

- `docs/product/158_C16_2_C17_VALIDATION_GATES.md`
- `docs/product/159_C16_2_UX_PDCA_PROCESS.md`
- `docs/product/160_C16_2_SYNTHETIC_USER_UX_REVIEW.md`
