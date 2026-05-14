# 153 - C16.1 - Screen Intent Map

## Purpose

Every screen must have a job. This map prevents screens from becoming a mix of
technical status, instructions and diagnostics. It also tells QA what to test.

## Screen Catalog

### boot

- Journey: A/O.
- Intention: Show appliance started.
- Target user: all.
- Technical state: boot initial.
- Perceived state: initializing.
- Primary action: wait.
- Max wait: 3s.
- Owner: `totem_visual_splash.py`.
- Test method: offline SVG + HDMI.
- Risk: medium.

### firstboot

- Journey: A/B.
- Intention: Prepare first use safely.
- Target user: installer.
- Technical state: firstboot gate.
- Perceived state: preparing.
- Primary action: wait.
- Max wait: 3s.
- Owner: `totem_firstboot_gate.sh`.
- Test method: grep + boot.
- Risk: medium.

### preparing

- Journey: A/O.
- Intention: Cover service startup.
- Target user: all.
- Technical state: services starting.
- Perceived state: preparing.
- Primary action: wait.
- Max wait: 5s.
- Owner: splash.
- Test method: timeline.
- Risk: low.

### config_missing

- Journey: B.
- Intention: Say config is missing.
- Target user: installer.
- Technical state: no real config.
- Perceived state: action needed.
- Primary action: F10.
- Max wait: 0s.
- Owner: launcher/status.
- Test method: clean-board.
- Risk: medium.

### config_pending

- Journey: B.
- Intention: Hold safe F10 prompt.
- Target user: installer.
- Technical state: no real config.
- Perceived state: ready to configure.
- Primary action: F10.
- Max wait: 0s.
- Owner: status renderer.
- Test method: clean-board.
- Risk: low.

### F10/open settings

- Journey: L.
- Intention: Confirm transition to setup.
- Target user: installer.
- Technical state: trigger/session.
- Perceived state: opening setup.
- Primary action: wait.
- Max wait: 3s.
- Owner: settings session.
- Test method: trace + HDMI.
- Risk: medium.

### wizard orientation

- Journey: C.
- Intention: Select display orientation.
- Target user: installer.
- Technical state: wizard step.
- Perceived state: choosing.
- Primary action: Enter.
- Max wait: 0s.
- Owner: wizard.
- Test method: gallery/manual.
- Risk: low.

### wizard connection

- Journey: C.
- Intention: Select connection path.
- Target user: installer.
- Technical state: wizard step.
- Perceived state: choosing network.
- Primary action: Enter.
- Max wait: 0s.
- Owner: wizard.
- Test method: gallery.
- Risk: low.

### Wi-Fi list

- Journey: D/F.
- Intention: Pick strongest usable network.
- Target user: installer.
- Technical state: Wi-Fi scan/list.
- Perceived state: choosing Wi-Fi.
- Primary action: Enter.
- Max wait: 10s.
- Owner: Wi-Fi adapter.
- Test method: self-test/manual.
- Risk: medium.

### Wi-Fi password

- Journey: E.
- Intention: Enter secret safely.
- Target user: installer.
- Technical state: secure field.
- Perceived state: hidden password.
- Primary action: Enter.
- Max wait: 0s.
- Owner: wizard.
- Test method: input stress.
- Risk: medium.

### environment

- Journey: C.
- Intention: Enter environment value.
- Target user: installer.
- Technical state: text field.
- Perceived state: required field.
- Primary action: Enter.
- Max wait: 0s.
- Owner: wizard.
- Test method: input stress.
- Risk: medium.

### review

- Journey: C/H.
- Intention: Confirm before write.
- Target user: installer.
- Technical state: summary.
- Perceived state: review.
- Primary action: Enter saves.
- Max wait: 0s.
- Owner: wizard.
- Test method: gallery.
- Risk: low.

### saving

- Journey: H.
- Intention: Show writer is active.
- Target user: installer.
- Technical state: writer running.
- Perceived state: saving.
- Primary action: wait.
- Max wait: 5s.
- Owner: wizard/splash.
- Test method: trace.
- Risk: medium.

### complete

- Journey: H.
- Intention: Confirm setup passed.
- Target user: installer.
- Technical state: writer passed.
- Perceived state: done.
- Primary action: wait.
- Max wait: 3s.
- Owner: wizard.
- Test method: trace.
- Risk: low.

### error

- Journey: E/K/N.
- Intention: Explain recoverable failure.
- Target user: installer/support.
- Technical state: error state.
- Perceived state: action needed.
- Primary action: retry/support.
- Max wait: 0s.
- Owner: wizard/status.
- Test method: negative tests.
- Risk: high.

### starting_player

- Journey: H/M.
- Intention: Announce player handoff.
- Target user: all.
- Technical state: service starting.
- Perceived state: starting player.
- Primary action: wait.
- Max wait: 3s.
- Owner: launcher.
- Test method: timeline.
- Risk: medium.

### loading_content

- Journey: G/I/S.
- Intention: Cover wait for API/cache/media.
- Target user: all.
- Technical state: startup wait.
- Perceived state: loading content.
- Primary action: wait.
- Max wait: 5s.
- Owner: player + core.
- Test method: timeline + HDMI.
- Risk: medium.

### waiting_for_api

- Journey: G/R.
- Intention: Classify backend wait.
- Target user: support/user.
- Technical state: API pending.
- Perceived state: loading content.
- Primary action: wait.
- Max wait: 5s.
- Owner: player status.
- Test method: outage simulation.
- Risk: medium.

### waiting_for_media

- Journey: I/K/T.
- Intention: Classify media/cache wait.
- Target user: all.
- Technical state: media pending.
- Perceived state: preparing media.
- Primary action: wait.
- Max wait: 5s.
- Owner: player status.
- Test method: no-cache scenario.
- Risk: high.

### playing

- Journey: J.
- Intention: Normal operation.
- Target user: spectator.
- Technical state: MPV playing.
- Perceived state: content.
- Primary action: none.
- Max wait: 10s.
- Owner: kiosky-player.
- Test method: runtime timeline.
- Risk: low.

### player_error

- Journey: K/T.
- Intention: Avoid black failure.
- Target user: all.
- Technical state: player/no content error.
- Perceived state: content unavailable.
- Primary action: support/retry.
- Max wait: 5s.
- Owner: player/core.
- Test method: negative scenario.
- Risk: high.

### update_checking

- Journey: M.
- Intention: Show update check.
- Target user: support/user.
- Technical state: updater checking.
- Perceived state: checking.
- Primary action: wait.
- Max wait: 10s.
- Owner: updatectl.
- Test method: status test.
- Risk: medium.

### update_applying

- Journey: M.
- Intention: Show update apply.
- Target user: support/user.
- Technical state: updater applying.
- Perceived state: updating.
- Primary action: wait.
- Max wait: 10s.
- Owner: updatectl.
- Test method: update test.
- Risk: high.

### update_failed

- Journey: N.
- Intention: Show safe failure/rollback.
- Target user: support/user.
- Technical state: updater failed.
- Perceived state: not updated.
- Primary action: retry/support.
- Max wait: 0s.
- Owner: updatectl.
- Test method: failure test.
- Risk: medium.

### maintenance/support

- Journey: P/Q.
- Intention: Provide safe support path.
- Target user: support.
- Technical state: diagnostic state.
- Perceived state: support needed.
- Primary action: collect status.
- Max wait: 0s.
- Owner: remote probes.
- Test method: runbook.
- Risk: medium.

## Acceptance Pattern

A screen is acceptable for homologation when:

- the main message matches the perceived state;
- the primary action is visible or the wait is explicit;
- no secret or raw technical value can appear;
- the owner and test method are clear;
- the journey has a recovery path.
