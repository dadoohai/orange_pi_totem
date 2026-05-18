# 175 - C18.2 - Player Duration Field Normalization

Status: passed

C18.2 makes a small, testable correction to `kiosky-player` duration semantics
using the C18.1 fake API, fake MPV and deterministic clock harness. It does not
use Orange Pi hardware, does not publish a release, does not build an image and
does not change wizard, totem-core, scheduler, sync or playlist ordering.

## Duration Contract

Canonical field:

- `exposure_time_ms`: milliseconds.

Accepted aliases:

- `exposureTimeMs`: milliseconds.
- `exposureTimeSeconds`: seconds, converted to milliseconds.

Ambiguous field:

- `duration` is not accepted in C18.2.

Decision: `duration` remains ignored because the current local code and docs do
not prove whether it means seconds, milliseconds, real file duration or another
backend concept. Accepting it now could silently change playback windows.

Priority:

1. `exposure_time_ms`
2. `exposureTimeMs`
3. `exposureTimeSeconds`
4. `default_duration_ms`

Rules:

- Invalid, zero and negative values are ignored.
- A valid API duration is not overwritten by `default_duration_ms`.
- The selected source is tracked as one of:
  `exposure_time_ms`, `exposureTimeMs`, `exposureTimeSeconds` or `default`.
- The selected source is propagated through raw API items, downloaded
  `MediaItem`s, cache metadata, saved playlist state and public current/next
  item status.

## Short Video Policy

`short_video_policy=repeat_to_fill_exposure`

The selected policy is to keep the exposure window authoritative. If a video is
shorter than the selected exposure duration, MPV may repeat the file inside that
window because the player starts MPV with `--loop-file=inf`. Playback still
advances to the next playlist item at the end of the selected exposure window.

This keeps the C18.1 observed behavior but makes it explicit and tested instead
of accidental. It does not prove MPV/DRM/KMS hardware timing; that still requires
Orange Pi validation.

## Implementation

`kiosk.py` now has:

- `resolve_exposure_duration_ms(item, default_duration_ms) -> (duration_ms, source)`
- small positive-value parsers for millisecond and second fields
- `duration_source` on `MediaItem`

No scheduler, sync, playlist ordering or broad cache behavior was refactored.
The only playback status addition is the selected `duration_source` metadata.

## Tests

The C18.1 simulation tests were extended to cover:

- snake-case `exposure_time_ms`
- `exposureTimeMs`
- `exposureTimeSeconds`
- priority over aliases
- default fallback when fields are absent
- default not overriding valid API duration
- invalid values ignored
- ambiguous `duration` ignored
- duration source tracked
- short-video repeat-to-fill policy
- multi-item playlist advance at the end of the exposure window

Validation:

- `python3 -m py_compile kiosk.py tests/test_player_timing_simulation.py tests/fakes/player_simulation.py`
- `python3 -m unittest tests/test_player_timing_simulation.py`
- `python3 -m unittest discover -s tests`

## Result

`c18_2_status=passed`

`default_duration_overrides_api=false`

`short_video_policy=repeat_to_fill_exposure`

`ready_for_c18_3_release_package=true`

`ready_for_hardware_player_validation=true`

## Still Requires Orange Pi

- Real MPV DRM/KMS startup and IPC behavior.
- HDMI and flicker perception.
- Hardware decode behavior when a short video loops inside the exposure window.
- Systemd timing on the appliance.
- C17.7 hardware boot validation.
- Wi-Fi/NetworkManager, F10 physical path, read-only/C12 and power-cut/C12.4.
