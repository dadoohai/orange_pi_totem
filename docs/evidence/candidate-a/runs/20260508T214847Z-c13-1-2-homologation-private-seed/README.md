# C13.1.2 - Homologation Private Seed

Data: 2026-05-08

## Summary

```text
c13_1_2_status=code_and_board_hotfix_passed_private_image_build_pending
artifact_private=true
final_image=false
homologation_private_values_embedded=false
homologation_private_values_supported=true
seed_source_outside_repo=true
seed_permissions_ok=true
seed_embedded_path=/data/state/totem-settings/private-values.seed.json
seed_content_published=false
wizard_auto_policy_enabled=true
writer_called=true
real_config_written=true
config_real_present=true
public_state_after_apply=player_running
playback_after_apply=playing
ready_for_multi_card_homologation=false
ready_for_c13_1_2_private_image_build=true
c12_readonly_blocked=true
c12_4_blocked=true
poweroff_executed=false
power_cut_tested=false
apt_update_executed=false
apt_upgrade_executed=false
secrets_published=false
```

## What Changed

- Added a lab-only apply-policy helper for homologation private seeds.
- Added automatic policy creation before the F10 wizard when the seed exists.
- Added wizard copy that clearly indicates homologation apply mode without showing private values.
- Allowed the handoff to read the single approved seed path under `/data/state/totem-settings`.
- Added build support and offline validation for a private homologation image-lab artifact.

## Board Hotfix Result

The currently booted lab board was patched without reboot or package changes.
A private seed file supplied outside the repository was validated by category and
permission only, copied to the approved seed path, and used to refresh the real
config through the writer.

Sanitized result:

```text
writer_result=passed
writer_phase=completed
config_real_present=true
public_state=player_running
playback=playing
seed_content_published=false
secret_values_published=false
```

## Image Build Status

A private image-lab build was not executed in this commit. The build path is now
ready for a follow-up run with:

```text
C13_EMBED_HOMOLOG_PRIVATE_VALUES=1
C13_HOMOLOG_PRIVATE_VALUES=<outside-repo-private-file>
C13_CONFIRM_PRIVATE_HOMOLOG_IMAGE=1
```

## Guardrails

No private values, real config content, SSID/password, IP/MAC/DNS, raw logs,
firstboot.conf contents, API key, API URL value, or environment identifier were
recorded in this evidence.
