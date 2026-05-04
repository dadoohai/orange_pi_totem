# C9.9.1 Visual Latency Fix Evidence

Date: 2026-05-04

Commit under test: local working tree after C9.9 checkpoint `6411e92`.

## Commands

- `git status --short`
- `git diff --check`
- `bash -n scripts/remote/run_c9_9_visual_wizard.sh`
- `bash -n scripts/remote/run_c9_9_1_visual_latency_probe.sh`
- `python3 scripts/board/totem_setup_visual_wizard.py --self-test`
- `python3 scripts/board/totem_visual_render_latency_probe.py --self-test`
- `python3 scripts/board/totem_config_contract_validate.py --self-test`
- `scripts/remote/run_c9_9_1_visual_latency_probe.sh <host> --prepare-only --mpv-video-mode drm`
- `scripts/remote/run_c9_9_1_visual_latency_probe.sh <host> --probe --mpv-video-mode drm`
- `scripts/remote/run_c9_9_1_visual_latency_probe.sh <host> --run-visual-wizard-latency-check --method restart_mpv_unique_path --mpv-video-mode drm`
- `scripts/remote/run_c9_9_1_visual_latency_probe.sh <host> --run-visual-wizard-latency-check --method unique_path_ipc_wait --mpv-video-mode drm`
- `scripts/remote/run_c9_9_visual_wizard.sh <host> --prepare-only`
- `scripts/remote/run_c9_9_visual_wizard.sh <host> --run-cancel --timeout-sec 300`
- `scripts/remote/run_c9_9_visual_wizard.sh <host> --run-complete-existing-wifi --timeout-sec 1800`

## Results

- Probe classified the original path as `mpv_ipc_load_not_presenting_immediately`.
- Human HDMI validation confirmed MPV restart mode changed screens on the first
  input but flashed to TTY/shell between updates.
- Human HDMI validation confirmed MPV IPC mode avoided restart but remained one
  input behind.
- Final accepted path uses `framebuffer_svg`: characters appeared, Enter worked
  on first input, and no shell flash was observed during typing.
- `PgDn` accidental input was handled without cancelling after the patch.
- Cancel flow passed.
- Complete flow passed with existing dedicated Wi-Fi.
- Candidate was generated under `/tmp`.
- C5.1 `--allow-mock` passed.
- C5.1 `--real-dry-run` failed as expected while placeholders remain.

## Final State

- service: `active/enabled`
- NRestarts: `0`
- public_state: `player_running`
- playback: `playing`
- player category: active
- MPV category: active
- renderer/setup categories: absent from setup path
- visual_renderer: `framebuffer_svg`
- network_changed: `false`
- real_config_read: `false`
- real_config_written: `false`
- writer_called: `false`

## Not Altered

- real config was not read or written;
- writer was not called;
- Wi-Fi profile was not changed;
- hotspot and portal were not created;
- `kiosky-player` repository was not changed;
- no reboot was performed;
- no raw config candidate, SSID, password, IP, MAC, gateway, DNS, hostname,
  UUID, API key, real API URL, environment identifier, private media path or raw
  logs are included here.
