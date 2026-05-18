# 173 - C17.8 - Simulation Coverage Matrix

Status: baseline matrix for simulation-first QA

This matrix separates what C17.8 can validate locally from what still requires
Orange Pi Zero 3 hardware. Local confidence is useful for regression control,
but hardware homologation remains mandatory before batch, dispatch or C18.

| Item | can_test_locally | method | confidence | requires_orange_pi | next_harness |
| --- | --- | --- | --- | --- | --- |
| rootfs layout | true | debugfs/rootfs inspection and path/hash checks | high | false | `c17_8_compare_image_boot_artifacts.py` |
| boot artifacts | partial | sfdisk/debugfs/stat/sha256 comparison of partition table, U-Boot region, `/boot`, kernel, DTB, initrd and boot scripts | medium | true | boot artifact diff plus clean-card boot |
| totem-core apply/rollback | true | `.sim/totem` fake `/data`, `/run`, `/tmp` with apply-local, current/previous and rollback | high | false | `run_totem_core_sandbox.py` |
| wizard input replay | partial | planned keyboard/input replay against wizard code, no real HDMI/F10 ownership yet | medium | false | `run_wizard_input_replay.py` |
| splash/status SVG | true | render/self-test/status contract checks and generated SVG artifacts | high | false | existing visual QA plus C17.8 replay |
| fake API / environments | true | local HTTP/fake endpoint responses for `/environments/:id` style validation | medium | false | C17.8.1 wizard replay |
| fake `/search` | true | local fake content preflight responses for empty/error/success paths | medium | false | C17.8.1 wizard replay |
| kiosky-player unit tests | true | `python3 -m unittest discover -s tests` in `kiosky-player` | high | false | existing unit suite |
| fake MPV/API | partial | planned fake MPV IPC and fake API state machine, no DRM/KMS | medium | false | `run_player_fake_mpv_api.py` |
| MPV DRM/KMS real | false | requires real mpv with DRM/KMS device and HDMI output | high | true | Orange Pi runtime probe |
| Wi-Fi real | false | requires real radio, credentials, RF environment and NetworkManager apply | high | true | Orange Pi Wi-Fi validation |
| NetworkManager real | partial | adapter syntax/self-test locally; real profile/apply requires device | medium | true | Orange Pi NetworkManager validation |
| F10 fisico | false | requires physical keyboard/input path and visual ownership on tty/HDMI | high | true | clean-card Orange Pi first boot |
| HDMI/flicker | false | requires real display, cable, DRM/KMS timing and human/visual observation | high | true | Orange Pi HDMI validation |
| U-Boot/kernel/DTB boot | false | local hashes can compare artifacts, but only hardware proves boot | high | true | clean-card Orange Pi boot |
| read-only/C12 | false | blocked by C12 decision and requires dedicated hardware/image path | high | true | C12 remains blocked |
| power cut/C12.4 | false | blocked until read-only is solved and physical power-cut protocol exists | high | true | C12.4 remains blocked |

## Current decision

`ready_for_c17_8_1_wizard_replay=true`

`ready_for_c18_1_player_sim_audit=true`

`hardware_homologation_required=true`

Simulation should continue for wizard replay and fake player/API harnesses, but
it cannot replace Orange Pi clean-card boot, HDMI/F10, Wi-Fi, NetworkManager,
MPV DRM/KMS, read-only or power-cut validation.
