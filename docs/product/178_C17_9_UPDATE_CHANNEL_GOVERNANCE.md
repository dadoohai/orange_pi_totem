# 178 - C17.9 - Update Channel Governance

> Regras atuais de atualizacao C18 estao consolidadas em
> [docs/UPDATE_CONTRACT.md](../UPDATE_CONTRACT.md). Este documento segue como
> base historica da politica de canais.

Date: 2026-05-18

Status: passed

## Purpose

C17.9 defines how remote updates are selected before any real GitHub Release is
published for `kiosky-player` or `totem-core`. The goal is to prevent a lab or
homologation package from being applied accidentally on customer devices.

No GitHub Release, remote tag, board access, card write, image build, apt, pip,
kernel, U-Boot, DTB, BSP, C12/read-only, wizard UX change or player timing
change was performed.

## Current Update Selection Behavior

Before C17.9, `totem_updatectl.py` listed GitHub Releases, ignored drafts and
selected the newest release with an asset named
`dadooh-<component>-*.manifest.json`. It did validate manifest schema,
component, payload SHA and device requirements before apply, but it did not
require `channel`, did not compare manifest channel with device policy, and did
not reject prereleases for stable devices.

The publish scripts already inferred prerelease from `channel != stable`, but
that was publication metadata only. The device-side updater did not yet enforce
the channel contract.

## Channel Policy

C17.9 uses a conservative exact-channel policy:

| device_channel | accepted manifest channel | prerelease |
| --- | --- | --- |
| `stable` | `stable` only | rejected |
| `homologation` | `homologation` only | accepted only if policy allows |
| `lab` | `lab` only | accepted only if policy allows |

This is intentionally stricter than inheritance (`lab` accepting all channels).
Promotion must be explicit: `lab -> homologation -> stable`.

Channel meanings:

- `lab`: local development and sandbox packages. Prefer local-only packages.
  Real GitHub Releases require explicit authorization and must not be stable.
- `homologation`: test boards only. Can be prerelease. Never accepted by
  `stable` devices.
- `stable`: customer devices only. Must be a normal release and requires prior
  physical homologation.

## Device Policy

The device policy file is:

`/data/updates/policy.json`

Schema:

```json
{
  "schema": "dadooh.totem.update.policy.v1",
  "device_channel": "stable",
  "allowed_components": ["kiosky-player", "totem-core"],
  "allow_prerelease": false,
  "allow_downgrade": false
}
```

Rules:

- Missing policy defaults to `device_channel=stable`.
- Invalid policy fails closed to stable with `allow_prerelease=false`.
- The policy contains no secrets.
- `allowed_components` must explicitly include the component being applied.

## Manifest Contract

Both components use manifest schema `dadooh.totem.update.v1` and must include:

- `schema`
- `component`
- `version`
- `channel`
- `source_repo`
- `source_commit`
- `payload`
- `payload_sha256`
- `created_at` or `created_at_utc`
- `requires.device`
- `requires.base_image_min` or component equivalent

`build_kiosky_player_release_package.sh` and
`build_totem_core_release_package.sh` now accept only:

- `lab`
- `homologation`
- `stable`

## Updater Enforcement

`scripts/board/totem_updatectl.py` now enforces:

- component filter before selection;
- manifest channel is required;
- manifest channel must match device policy exactly;
- draft releases are ignored;
- prerelease releases are ignored unless policy allows prerelease;
- releases without matching component assets are ignored;
- releases with invalid manifest schema/component/channel/SHA are ignored;
- local apply also enforces the same channel policy;
- `status` reports the active update policy.

The updater also exposes dry-run selection:

```sh
totem-updatectl list-github --component kiosky-player --repo OWNER/REPO --dry-run
totem-updatectl apply-github-latest --component totem-core --repo OWNER/REPO --dry-run
```

Dry-run selection may fetch manifests for evaluation, but it does not alter
`state.json`, `current` or `previous`.

## Local Tests

Added:

`scripts/qa/c17_9_update_channel_policy_test.py`

Synthetic cases covered:

- stable device blocks lab;
- stable device blocks homologation;
- stable device accepts stable;
- homologation device accepts homologation when prerelease is allowed;
- homologation device blocks lab under conservative policy;
- lab device accepts lab when prerelease is allowed;
- cross-component `totem-core -> kiosky-player` blocked;
- cross-component `kiosky-player -> totem-core` blocked;
- release without valid manifest ignored;
- manifest without SHA ignored;
- draft release ignored;
- prerelease requires policy permission;
- dry-run selection does not mutate state/current/previous.

Result: 13 tests passed.

## Sandbox

C17.9 reused the C17.8 totem-core sandbox with `.sim/c17-9`.

Result:

- `apply_local_passed=true`
- `rollback_passed=true`
- `wrapper_current_passed=true`
- `wrapper_fallback_passed=true`
- `settings_lock_guard_passed=true`
- `channel_guard_compatible_passed=true`
- `channel_guard_incompatible_blocked=true`
- `writes_outside_sim_detected=false`

## Publication Rules

Lab:

- Prefer local package.
- If a GitHub Release is explicitly authorized, use draft or prerelease and
  manifest `channel=lab`.
- Never publish as stable.

Homologation:

- Use prerelease.
- Manifest `channel=homologation`.
- Only devices with `device_channel=homologation` and prerelease allowed apply
  it.

Stable:

- Use normal release.
- Manifest `channel=stable`.
- Requires local tests, sandbox apply/rollback and physical homologation first.
- Do not publish stable while `hardware_homologation_required=true`.

## Decision

`c17_9_status=passed`

`ready_for_c18_3_player_rc_package=true`

`ready_for_totem_core_publish=false`

`hardware_homologation_required=true`
