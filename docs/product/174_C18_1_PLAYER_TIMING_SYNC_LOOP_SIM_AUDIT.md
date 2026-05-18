# 174 - C18.1 - Player Timing Sync Loop Simulation Audit

Status: audit_only

C18.1 audits the `kiosky-player` timing/sync/loop behavior with fake API, fake
MPV and deterministic clock tests. It does not use Orange Pi hardware, does not
change production scheduler/sync/duration/loop logic, does not publish a
release, and does not touch totem-core, wizard or appliance image code.

## Current Model

### API/data model

The player calls `POST <api_url>` with a search payload containing
`environmentId`, `onlyStandby`, `searchIn`, `includeDescendants` and `limit`.
The request uses `x-api-key`, but tests and evidence keep this synthetic and do
not publish values.

The parser expects a response shaped as `units[] -> campaigns[]`. It accepts
campaigns whose `status` is empty, `active` or `ativa`. For each accepted
campaign it reads:

- `media_urls`, or `primary_media_url` when `media_urls` is empty;
- `exposure_time_ms` as the duration source;
- `id` and `name` for status/telemetry labels.

The current parser ignores `exposureTimeMs`, `exposureTimeSeconds` and
`duration`. If `exposure_time_ms` is absent or falsey, it uses
`default_duration_ms`.

### Duration

The effective playlist duration is `effective_duration_ms(item.duration_ms)`,
with a floor of `1000ms`.

- Image: uses the API/cache duration window; MPV itself has
  `--image-display-duration=inf`, so the player clock decides when to advance.
- Short video: uses the API/cache duration window. Because MPV starts with
  `--loop-file=inf`, a video shorter than `exposure_time_ms` can repeat inside
  the exposure window.
- Long video: the player advances at the selected duration window, independent
  of the file's real duration.
- Missing duration: falls back to `default_duration_ms`.
- Real media duration: not probed by the player in the current code path.

### Playlist

`PlaylistState` stores the current media list, version and fingerprints. On
playlist version changes, playback recalculates position. With sync enabled,
the player computes UTC cycle position; with sync disabled, it starts at index
0.

Playback advances by index after each selected duration. A one-item playlist
therefore repeats the same item by design. With multiple items, it advances to
the next item. If `preload_next=true`, it appends the next file to MPV and then
uses `playlist-next` plus `playlist-remove 0`; appliance config currently sets
`preload_next=false`.

Media load failure causes a restart and one retry. If retry fails, the item
enters cooldown and playback advances to the next available item. If every item
is blocked, public status becomes `waiting_for_media` with
`all_media_temporarily_blocked`.

### Cache/API

On poll success, the player downloads or validates media into `cache_dir`.
When `require_full_download_before_switch=true`, it only switches playlist
after all raw API items are available locally.

If API returns an empty playlist and `allow_empty_playlist_from_api=false`, the
player keeps the current playlist when one exists. If there is no current
playlist, it tries local cache. If neither current playlist nor cache exists,
the poller records a safe API error and the playback loop stays in
`waiting_for_media`/`waiting_for_playlist`.

On API timeout/error, the poller catches the exception, updates
`content_state=api_error_retrying`, increments `consecutive_failures`, and
keeps running.

### MPV

MPV is started once and controlled through IPC. Current startup flags include:

- `--idle=yes`
- `--keep-open=yes`
- `--loop-file=inf`
- `--image-display-duration=inf`
- `--input-ipc-server=<ipc_path>`

The player sends:

- `loadfile <path> replace` for current item;
- `loadfile <path> append` for preload;
- `playlist-next force`;
- `playlist-remove <index>`;
- `seek <seconds> absolute+exact` for sync offsets on videos;
- `set_property time-pos` fallback when seek fails;
- `get_property idle-active` for watchdog ping.

The current production loop does not consume MPV `end-file` or `file-loaded`
events as scheduler inputs. Timing is driven by the player monotonic clock.

### Sync/resync

The sync model anchors the global cycle at `00:05 UTC`. It computes
`(now_utc - anchor) % cycle_total` to select index and offset. Drift policy:

- below threshold: no correction;
- threshold to hard threshold: soft resync at the next item boundary;
- hard threshold or daily zero: immediate resync.

A hard resync can reload the same item when UTC target index is the current
item but offset differs. That can look like a loop if it happens repeatedly,
but the C18.1 stable-drift simulation did not detect same-item reload when
drift is zero.

### Public Status

The status model exposes public fields such as `player_state`,
`playback_state`, `startup_feedback_state`, `first_frame_ready`,
`content_state`, `current_item`, `next_item`, sync metadata and failure counts.
Startup/waiting states include `waiting_for_api`, `waiting_for_playlist`,
`waiting_for_media_cache`, `waiting_for_media`, `waiting_for_content` and
`error_no_content`.

## Simulated Scenarios

Implemented in `kiosky-player`:

- `tests/fakes/player_simulation.py`
- `tests/test_player_timing_simulation.py`

Executed scenarios:

1. `image_respects_exposure_time_ms`
2. `video_shorter_than_exposure_policy_is_mpv_loop_until_window`
3. `missing_exposure_uses_default`
4. `camel_case_duration_fields_are_ignored_by_current_parser`
5. `single_item_playlist_repeat_is_expected_cycle_behavior`
6. `multi_item_playlist_advances`
7. `api_empty_playlist_sets_waiting_for_media`
8. `api_timeout_does_not_crash_and_sets_safe_status`
9. `media_load_failure_advances_or_errors_cleanly`
10. `mpv_loop_flags_do_not_force_playlist_loop`
11. `sync_resync_does_not_restart_same_item_when_drift_is_stable`

All 93 local unit tests passed after adding the harness.

## Findings

`timing_semantics_status=default_duration_overrides_api`

Reason: if the backend sends `exposureTimeMs`, `exposureTimeSeconds` or
`duration` instead of `exposure_time_ms`, the current parser ignores those
fields and uses `default_duration_ms`. If the backend sends
`exposure_time_ms`, the current timing window is respected.

`looping_cause=mpv_loop_file`

Reason: MPV is started with `--loop-file=inf`. This is intentional enough for
images and single-item resilience, but it also means a short video can repeat
inside a longer exposure window. A one-item playlist also repeats by design;
that case should not be treated as a bug by itself.

`player_sim_confidence=high`

Confidence is high for code-level semantics and low-level command selection.
It does not validate DRM/KMS, HDMI, MPV real event timing or hardware decoding.

## What Was Proven Locally

- Snake-case `exposure_time_ms` is used as the selected duration.
- Missing or unsupported duration fields fall back to `default_duration_ms`.
- The player does not inspect real video duration.
- Short videos can repeat inside the exposure window because MPV has
  `--loop-file=inf`.
- Multi-item playlists advance in the simulated model.
- One-item playlists repeat as expected cycle behavior.
- Empty playlist/no cache leads to `waiting_for_media`/`waiting_for_playlist`.
- API timeout is caught and produces safe public status.
- Media load failure retries, then advances/errors cleanly.
- MPV loop is per-file; no `--loop-playlist=inf` was found.
- Stable sync drift does not request resync.

## Still Requires Orange Pi

- Real MPV DRM/KMS startup and IPC behavior.
- HDMI flicker/black-screen perception.
- Hardware decode timing and short-video end behavior on the board.
- Real content download/network variability.
- Systemd service timing.
- C17.7 hardware boot validation.
- Wi-Fi/NetworkManager, F10 physical path, read-only/C12 and power-cut/C12.4.

## C18.2 Proposal

C18.2 should be a targeted diagnostic/fix round, not a broad refactor:

- Decide the canonical duration field contract with backend:
  `exposure_time_ms` only, or accept aliases `exposureTimeMs`,
  `exposureTimeSeconds` and `duration`.
- Add a small duration normalization function with tests if aliases must be
  supported.
- Decide policy for short videos:
  keep loop-until-exposure, freeze/keep-open after end, or advance at real
  video end.
- If short-video repetition is undesired, evaluate removing or conditionally
  overriding `--loop-file=inf` for videos while preserving image behavior.
- Add optional runtime instrumentation for sanitized timing events before any
  production release.

No kiosky-player release should be prepared until C18.2 chooses and tests the
intended semantics.
