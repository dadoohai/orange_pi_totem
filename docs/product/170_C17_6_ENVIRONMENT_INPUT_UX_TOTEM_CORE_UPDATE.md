# 170 - C17.6 - Environment Input UX via Totem-Core Update

Status: passed

C17.6 is the first real UX update delivered through the `totem-core` remote
update path created in C17.5. It does not generate a new image and does not
touch scheduler, sync, duration, playlist, loop or `exposure_time_ms`.

## Scope

The update changes the visual setup wizard environment step only:

- editable `environment_id` field with a visible cursor;
- left/right cursor movement;
- Backspace and Delete in the middle of the value;
- Ctrl+U clear;
- Home/End cursor movement when the keyboard sends those sequences;
- local UUID format validation before any API call;
- optional remote validation through `/environments/:id`;
- content preflight through `/search`;
- warning, not hard failure, when `/search` returns no active content.

The Wi-Fi password field keeps the C15 behavior: `V` and `v` remain printable,
and show/hide stays on F2/Ctrl+P.

## Validation Policy

Local format validation is strict:

`environment_id` must be a canonical UUID.

Remote validation is private and sanitized:

- `/environments/:id` 200 means the environment exists;
- `/environments/:id` 404 blocks the flow as environment not found;
- `/environments/:id` 400 blocks as invalid ID;
- 401/403 or timeout are treated as validation unavailable;
- unavailable validation can continue only after explicit local confirmation;
- `/search` `total > 0` confirms content is available;
- `/search` `total = 0` warns "Sem midia ativa agora" but does not mark the
  environment invalid.

The wizard does not print real `api_url`, `api_key`, environment ID, media URLs,
SSID, password, IP, MAC or DNS in public status or evidence.

## Package

Component:

`component=totem-core`

Version:

`c17.6-environment-input-20260514T211247Z`

Release tag:

`totem-core-c17.6-environment-input-20260514T211247Z`

Payload SHA256:

`e6b643429709ba9f747d86bb113abc35ab9645da23216eb81455dbc2f5a9acb9`

Local apply with `totem-updatectl apply-local --component totem-core` passed
health checks in a builder sandbox.

## Runtime Validation

Board validation passed:

- physical F10 after C17.5 bootstrap opened the wizard;
- the published C17.6 release applied remotely to `/data/core/totem/current`;
- the wizard self-test passed from the updated wrapper path;
- the operator confirmed cursor/editing/Ctrl+U/validation UX on HDMI;
- the operator completed the normal wizard flow;
- post-run state showed settings lock absent, `totem-open-settings.service`
  inactive, player active and playback restored to `playing`;
- SSH and NetworkManager remained active.

Rollback was deferred because C17.5 already proved rollback for `totem-core`
and the lab board should remain on the validated C17.6 release for the next
round.

## Decision

`c17_6_status=passed`

`ready_for_c18_player_audit=true`

`ready_for_c17_7_image_embed_totem_core=true`

## Follow-Up

C17.7 built a new private homologation image with this C17.6 totem-core release
embedded as `/data/core/totem/current`, with wrappers and `/opt` fallback
present from first boot. See
`docs/product/171_C17_7_TOTEM_CORE_EMBEDDED_IMAGE_BUILD.md`.
