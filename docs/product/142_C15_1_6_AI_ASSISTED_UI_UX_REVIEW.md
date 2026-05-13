# 142 - C15.1.6 - AI-assisted UI/UX review

## Status

```text
c15_1_6_status=passed
manual_interaction_required=false
ready_for_image_rebuild=true
ready_for_c16_player_audit=true
c16_started=false
```

C15.1.6 was opened after C15.1.5 to turn the broader wizard visual PDCA idea
into a reproducible, non-interactive review. No operator keypress, HDMI
observation, reboot, writer call, Wi-Fi change, player change, apt, pip,
read-only, kernel, poweroff, or power-cut test was performed.

## Method

The new QA generator creates a synthetic gallery and review reports from the
existing renderers:

```text
scripts/qa/generate_ui_ux_gallery.py
```

Generated coverage:

- splashes: `boot`, `firstboot`, `preparing`, `player`, `setup`, `saving`,
  `config_pending`, `reboot`, `shutdown`;
- wizard: orientation landscape/portrait, network choice, Wi-Fi empty/short/
  long/paged/refresh/failure states, password hidden/visible, environment,
  review, saving, complete, cancel, and error.

The analysis is intentionally heuristic. It reads structured screen metadata,
transition metadata, and generated SVGs, then computes text/action/feedback
metrics and a per-screen rubric. It does not claim real pixel-level visual
inspection:

```text
ai_visual_review_performed=false
heuristic_review_performed=true
human_review_required=true
hdmi_capture_required_for_final_perception=true
```

PNG rasterization was attempted only with tools already present. `convert` was
available but did not successfully render the SVGs, so the evidence records
`png_render_available=false`.

## Findings

The non-interactive review found no P0 blocker:

```text
major_ui_blockers_found=false
p0_items_count=0
p1_items_count=4
p2_items_count=2
p3_items_count=1
```

The operator path is understandable screen by screen, every active wizard screen
has a primary action, editable/error states have a back/cancel path, and busy
states have explicit feedback in the synthetic gallery. Wi-Fi remains the
densest area because it is a paged list with signal metadata and actions.

Residual risks are not blockers for C15.2.1, but should stay visible:

- final perception of flicker, brief black screens, and rotation requires HDMI
  capture or camera;
- player waiting for media/cache/API can still benefit from a clearer public
  waiting state;
- wizard footers still feel technical because the appliance is operated by
  keyboard only;
- a future visual design-system pass is needed to move from functional wizard to
  more polished product UI.

## Methodology Levels

Nivel 1 - offline SVG/gallery: viable now; useful for copy, density, hierarchy,
and screen inventory.

Nivel 2 - automatic stress: viable now; useful for Backspace coalescing,
typing, pagination, refresh, password visibility, and splash mode coverage.

Nivel 3 - framebuffer: possible in some states over SSH, but limited for
MPV/DRM and not used in this card.

Nivel 4 - HDMI capture/camera: best method for flicker, black-screen gaps,
orientation changes, and user-perceived polish. This is future validation, not
a blocker for this non-interactive review.

## Decision

```text
ready_for_image_rebuild=true
ready_for_c16_player_audit=true
c16_started=false
```

C15.2.1 image rebuild remains released from the UI/UX side. C16/player audit
remains unstarted in this card and can be opened separately.

## Later Clean-Board Result

C15.2.1 proved that this heuristic review was not a substitute for real
clean-board setup validation. The image built and passed offline validation, but
the first clean-board wizard flow exposed a latent setup bug after Wi-Fi/NTP
time correction. C15.2.2 fixed that wizard timeout bug and removed printable
`V`/`v` as a password visibility shortcut, but a later post-wizard black-screen
and SSH-loss window required a physical power cycle. Batch flash, dispatch, and
C16 remain blocked until that window is classified.

## Evidence

`docs/evidence/candidate-a/runs/20260513T182524Z-c15-1-6-ai-ui-ux-review/`
