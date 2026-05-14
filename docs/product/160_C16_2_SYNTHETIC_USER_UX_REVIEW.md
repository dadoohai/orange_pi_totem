# 160 - C16.2 - Synthetic User UX Review

## Status

```text
c16_2_status=passed
manual_interaction_required=false
board_accessed_via_ssh=false
runtime_changed=false
gallery_generated=true
png_render_available=false
synthetic_user_runs_count=75
journeys_scored_count=15
screens_scored_count=25
p0_items_count=0
p1_items_count=5
ready_for_c17_image=true
need_c16_3_runtime_probes_before_c17=false
need_c16_4_visual_fix_before_c17=false
blocked_p0_user_journey=false
```

C16.1 created the product/UX operating model: personas, journeys, screen intent
map, UX/UI rubric, AI-assisted QA architecture and prioritized backlog. C16.2
made that model executable with an offline harness and synthetic-user review.

## Harness

New executable:

```text
scripts/qa/c16_2_synthetic_user_ux_review.py
```

It loads the C16.1 model, generates/reuses the UI/UX gallery, scores critical
journeys and screens, simulates synthetic users and writes a prioritized gap
backlog plus C17 validation gates.

Evidence run:

```text
docs/evidence/candidate-a/runs/20260514T050006Z-c16-2-synthetic-user-ux-review/
```

## Synthetic Users

- `installer_rushed`: wants fast setup, may type the wrong Wi-Fi password and
  does not read long text.
- `installer_cautious`: reads instructions and needs clear back/cancel paths.
- `support_remote`: does not see HDMI and depends on public status categories.
- `spectator`: does not interact; black or technical states break trust.
- `customer_receiver`: judges whether the appliance feels like a final product.

## Worst Results

- Worst journey: T - Estado sem cache, score 3.6/5.
- Lowest dimension on worst journey: negative path coverage, 2.9/5.
- Worst screen: `wifi_list`, score 4.3/5.
- Critical screens below 4: false.

The worst journey is not a P0 because it now has a mandatory C17 gate and does
not require player timing/sync/duration/loop changes. It remains a P1 until C17
proves the no-cache/no-content path with public-safe status.

## P1 Gates

- Negative API/cache/content scenarios became `C17-GATE-API-CACHE-CONTENT`.
- Wi-Fi wrong password and weak Wi-Fi became `C17-GATE-WIFI-NEGATIVE`.
- Update checking/applying/failed UX became `C17-GATE-UPDATE-UX`.
- HDMI/camera methodology became a scale gate, optional before C17.
- Wizard visual consistency became `C17-GATE-WIZARD-VISUAL-CONSISTENCY`.

## Decision

C17 can start now:

```text
ready_for_c17_image=true
```

C16.3 runtime probes are not mandatory before C17 because the runtime-dependent
P1 items are now expressed as C17 gates. C16.4 visual fix is not mandatory
because no critical screen scored below 4.

## Remaining Limitation

C16.2 is an offline/synthetic review. It cannot prove HDMI perception, flicker,
black frames or first-frame timing. HDMI/camera evidence remains required
before scale and should be recorded during or after C17 validation when
available.

## C17.1 Follow-Up

C17.1 used the C16.2 gates during clean-board homologation and passed the
image/setup validation. The negative API/cache/content, Wi-Fi and update paths
were exercised through the C16.2 harness/gallery plus safe public-status checks;
no destructive fault injection was applied on the configured board.

```text
c17_1_status=passed
ready_for_batch_flash=true
ready_for_dispatch=true
ready_for_c18_player_audit=true
```

See:

```text
docs/product/161_C17_1_HOMOLOG_UX_GATED_IMAGE_VALIDATION.md
```
