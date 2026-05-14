# 163 - C17.2 - Visual Design Pass

## Status

```text
c17_2_status=passed
decision=passed_visual_polish
visual_design_system_created=true
visual_polish_applied=true
gallery_generated=true
gallery_screen_count=53
png_render_available=false
board_accessed_via_ssh=false
runtime_changed=false
ready_for_c17_3_image_rebuild=true
ready_for_c18_player_audit=false
```

C17.1 passed as functional image validation, but it was not a meaningful visual
redesign. C17.2 is the first explicit visual polish pass for the appliance
surfaces: wizard, splashes and public status screens.

## Design System

C17.2 created the mini design system:

```text
docs/product/162_C17_2_VISUAL_DESIGN_SYSTEM.md
```

The design system keeps existing fonts, SVG primitives and framebuffer-safe
shapes. It standardizes dark appliance surfaces, accent rails, active cards,
footer action chips, support panels and public status language.

## Visual Changes

- Wizard screens now use a shared visual token set and a darker product shell.
- Step indicators and selected options use accent rails instead of bright
  inverted white cards.
- Info panels and input panels use consistent borders, rails and muted body
  text.
- Footers now separate the primary action from secondary shortcuts.
- Splash runtime rendering and preview SVGs use a centered product panel instead
  of only text on a flat background.
- Status preview replaces the placeholder/support-side panel with explicit
  support guidance: public state only, no private data and F10 as local action.
- The synthetic UI/UX gallery now renders C16.2 state screens with the same
  C17.2 appliance visual system.

## Before / After Rubric

```text
worst_screen_before=wifi_list
worst_screen_score_before=4.3
worst_screen_after=wifi_list
worst_screen_score_after=4.3
worst_journey_before=T
worst_journey_score_before=3.6
worst_journey_after=T
worst_journey_score_after=3.6
critical_screens_below_4=false
visual_scores_regressed=false
```

The C16.2 rubric is mostly structural, so it does not fully credit pixel-level
polish. The important gate result is no regression: no critical screen fell
below 4, and no critical journey score worsened.

## Gallery

Gallery evidence:

```text
docs/evidence/candidate-a/runs/20260514T060801Z-c17-2-visual-design-pass/gallery/
```

Required states are present as SVG: boot, config pending, Wi-Fi list, Wi-Fi
password hidden/visible, environment, review, saving, complete,
starting_player, loading_content, error_no_content and update_failed. PNG
rasterization was not available without installing dependencies.

## Remaining Limits

HDMI/camera capture is still required before scale. C17.2 validates visual
structure and generated SVGs, not camera-perceived flicker, black-frame timing
or HDMI exposure. C18 remains closed because player timing/sync/duration/loop
work is outside this round.

## Decision

```text
passed_visual_polish=true
ready_for_c17_3_image_rebuild=true
ready_for_c18_player_audit=false
```

C17.3 can rebuild/derive an image carrying this UI polish. C18 should remain
blocked until the C17.2/C17.3 visual line is closed.

## C17.3 Follow-Up

C17.3 derived the private homologation image
`c17-3-homolog-visual-polish` with the C17.2 visual polish embedded and passed
offline rootfs/harness validation. Clean-board validation is still blocked until
the image is manually flashed with Armbian Imager and booted on the lab board.

```text
c17_3_status=blocked
image_built=true
card_written=false
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c18_player_audit=false
```
