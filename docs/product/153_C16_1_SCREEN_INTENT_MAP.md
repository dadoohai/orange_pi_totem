# 153 - C16.1 - Screen Intent Map

## Purpose

Every screen must have a job. This map prevents screens from becoming a mix of
technical status, instructions and diagnostics. It also tells QA what to test.

| screen_id | Journey | Intention | Target user | Technical state | Perceived state | Primary action | Max wait | Owner | Test method | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boot | A/O | Show appliance started | all | boot initial | initializing | wait | 3s | `totem_visual_splash.py` | offline SVG + HDMI | medium |
| firstboot | A/B | Prepare first use safely | installer | firstboot gate | preparing | wait | 3s | `totem_firstboot_gate.sh` | grep + boot | medium |
| preparing | A/O | Cover service startup | all | services starting | preparing | wait | 5s | splash | timeline | low |
| config_missing | B | Say config is missing | installer | no real config | action needed | F10 | 0s | launcher/status | clean-board | medium |
| config_pending | B | Hold safe F10 prompt | installer | no real config | ready to configure | F10 | 0s | status renderer | clean-board | low |
| F10/open settings | L | Confirm transition to setup | installer | trigger/session | opening setup | wait | 3s | settings session | trace + HDMI | medium |
| wizard orientation | C | Select display orientation | installer | wizard step | choosing | Enter | 0s | wizard | gallery/manual | low |
| wizard connection | C | Select connection path | installer | wizard step | choosing network | Enter | 0s | wizard | gallery | low |
| Wi-Fi list | D/F | Pick strongest usable network | installer | Wi-Fi scan/list | choosing Wi-Fi | Enter | 10s | Wi-Fi adapter | self-test/manual | medium |
| Wi-Fi password | E | Enter secret safely | installer | secure field | hidden password | Enter | 0s | wizard | input stress | medium |
| environment | C | Enter environment value | installer | text field | required field | Enter | 0s | wizard | input stress | medium |
| review | C/H | Confirm before write | installer | summary | review | Enter saves | 0s | wizard | gallery | low |
| saving | H | Show writer is active | installer | writer running | saving | wait | 5s | wizard/splash | trace | medium |
| complete | H | Confirm setup passed | installer | writer passed | done | wait | 3s | wizard | trace | low |
| error | E/K/N | Explain recoverable failure | installer/support | error state | action needed | retry/support | 0s | wizard/status | negative tests | high |
| starting_player | H/M | Announce player handoff | all | service starting | starting player | wait | 3s | launcher | timeline | medium |
| loading_content | G/I/S | Cover wait for API/cache/media | all | startup wait | loading content | wait | 5s | player + core | timeline + HDMI | medium |
| waiting_for_api | G/R | Classify backend wait | support/user | API pending | loading content | wait | 5s | player status | outage simulation | medium |
| waiting_for_media | I/K/T | Classify media/cache wait | all | media pending | preparing media | wait | 5s | player status | no-cache scenario | high |
| playing | J | Normal operation | spectator | MPV playing | content | none | 10s | kiosky-player | runtime timeline | low |
| player_error | K/T | Avoid black failure | all | player/no content error | content unavailable | support/retry | 5s | player/core | negative scenario | high |
| update_checking | M | Show update check | support/user | updater checking | checking | wait | 10s | updatectl | status test | medium |
| update_applying | M | Show update apply | support/user | updater applying | updating | wait | 10s | updatectl | update test | high |
| update_failed | N | Show safe failure/rollback | support/user | updater failed | not updated | retry/support | 0s | updatectl | failure test | medium |
| maintenance/support | P/Q | Provide safe support path | support | diagnostic state | support needed | collect status | 0s | remote probes | runbook | medium |

## Acceptance Pattern

A screen is acceptable for homologation when:

- the main message matches the perceived state;
- the primary action is visible or the wait is explicit;
- no secret or raw technical value can appear;
- the owner and test method are clear;
- the journey has a recovery path.
