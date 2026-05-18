# C17.8.2 Wizard UX Totem-Core RC Sandbox

Date: 2026-05-18

Status: passed

## Purpose

C17.8.1 changed runtime behavior in the visual wizard: navigation grammar,
shorter footers, Esc/back behavior in substeps, and local input replay coverage.
C17.8.2 packages those runtime changes as a local `totem-core` release
candidate and validates the update path in a local sandbox.

This is not a production release. No GitHub Release, tag, remote apply, image,
card write, SSH, board access, apt, pip, kernel, U-Boot, DTB, BSP, C12 or player
change was performed.

## Package

version=c17.8.2-wizard-ux-rc-20260518T202740Z
channel=lab
component=totem-core

Package directory:

`releases/core-updates/c17.8.2-wizard-ux-rc-20260518T202740Z/`

Files:

- `dadooh-totem-core-c17.8.2-wizard-ux-rc-20260518T202740Z.manifest.json`
- `dadooh-totem-core-c17.8.2-wizard-ux-rc-20260518T202740Z.tar.gz`

Validation:

- `schema=dadooh.totem.update.v1`
- `component=totem-core`
- `channel=lab`
- `source_repo=dadoohai/orange_pi_totem`
- `source_branch=foundation-v0.1`
- `source_commit=f0f67c6d84adb7d9a024bcb0544a5d5747b5cce0`
- `payload_sha256=4704e49f482cb52c1a1b5d697d22ee72ae71c9b403a8af5c8c3e05831abc11d2`
- payload SHA256 matched the manifest
- payload includes `bin/totem_setup_visual_wizard.py`
- payload excludes docs/evidence, config real, private-values, media and cache
- payload secrets scan passed for forbidden filenames and token/private-key
  patterns

## Sandbox Validation

Sandbox:

`.sim/c17-8-2`

Mode:

`repo_overlay`

The sandbox provided fake `/data`, `/run`, `/tmp`, `/opt/totem/bin`,
`/opt/totem/core-fallback/bin`, `/data/core/totem/releases`, `current`,
`previous` and evidence directories.

Result:

- `apply_local_passed=true`
- `current_symlink_updated=true`
- `previous_symlink_updated=true`
- `rollback_passed=true`
- `wrapper_current_passed=true`
- `wrapper_fallback_passed=true`
- `settings_lock_guard_passed=true`
- `apply_blocked_when_settings_active=true`
- final `current=releases/c17.8.2-wizard-ux-rc-20260518T202740Z`
- `writes_outside_sim_detected=false`

The lock guard test created a synthetic
`.sim/c17-8-2/run/totem/settings-session.lock`, verified that apply was blocked
before changing `current`, removed the lock and reapplied successfully.

## Replay Against Package

The input replay was executed with:

`--source .sim/c17-8-2/data/core/totem/current`

Scenarios:

- `happy_path_synthetic`
- `back_navigation`
- `environment_invalid_uuid`
- `environment_edit_middle`
- `wifi_wrong_password_fake`
- `api_unavailable_fake`
- `cancel_flow`

Result:

- `scenario_count=7`
- `screens_count=19`
- `assertions_count=14`
- `assertions_passed=true`
- `writer_called=false`
- `real_config_written=false`
- `secrets_published=false`

## Gallery

The UX gallery was generated with:

`--source .sim/c17-8-2/data/core/totem/current`

Result:

- `gallery_generated=true`
- `gallery_screen_count=53`
- `png_render_available=false`
- `critical_screens_below_4=false`
- `footer_consistency_score=4.6`
- `primary_action_clarity_score=4.5`
- `back_action_clarity_score=4.5`

## Remote Publication

Remote publication was intentionally skipped.

- `github_release_published=false`
- `remote_publish_skipped=true`
- `publish_reason_skipped=no_update_channel_governance_yet`

C17.8.2 proves the local package/update mechanics, but it does not yet define
who may publish, which channels are accepted by a device, how RCs graduate, or
how rollback policy is governed remotely. That belongs in C17.9.

## Hardware Limits

Still requires Orange Pi validation:

- physical F10 entry path
- HDMI readability, flicker and real rotation perception
- real Wi-Fi radio and NetworkManager apply
- real writer/config apply path
- MPV/DRM/KMS player behavior
- C17.7 boot validation
- power-cut behavior

C12/read-only and C12.4 remain blocked and were not touched.

## Decision

c17_8_2_status=passed

ready_for_c17_9_update_channel_governance=true

ready_for_c18_player_work=true

hardware_homologation_required=true
