# 152 - C16.1 - User Journeys

## Scope

This map defines the critical journeys that future UI/UX QA must score. It is
also the checklist C17 should use when validating the next consolidated image.

## Journey Catalog

### A - Primeira energizacao

- Success exit: feedback inicial appears.
- Error exit: black screen prolonged.
- Max no-feedback: 3s.
- Expected screen: boot.
- Recovery: support checks boot/power.
- Existing test: C15 splash validations.
- Missing test: HDMI/camera timing.

### B - Boot sem configuracao

- Success exit: config pending visible.
- Error exit: login/terminal visible.
- Max no-feedback: 3s.
- Expected screen: config_pending.
- Recovery: press F10/support.
- Existing test: C15.2.4 clean-board.
- Missing test: camera flicker check.

### C - Primeira configuracao via F10

- Success exit: config written/player restored.
- Error exit: wizard exits alone.
- Max no-feedback: 5s.
- Expected screen: wizard.
- Recovery: back/cancel/retry.
- Existing test: C15.2.4 full setup.
- Missing test: synthetic journey runner.

### D - Selecao de Wi-Fi

- Success exit: network selected.
- Error exit: list confusing.
- Max no-feedback: 10s.
- Expected screen: wifi_list.
- Recovery: R refresh/Esc.
- Existing test: C15.1.4.
- Missing test: offline visual regression.

### E - Senha Wi-Fi errada

- Success exit: user can retry.
- Error exit: technical failure.
- Max no-feedback: 5s.
- Expected screen: wifi_password_error.
- Recovery: retry/back.
- Existing test: partial.
- Missing test: negative board test.

### F - Wi-Fi fraco/instavel

- Success exit: signal risk visible.
- Error exit: unexplained drop.
- Max no-feedback: 10s.
- Expected screen: wifi_list.
- Recovery: choose stronger network.
- Existing test: C15.1.4 labels.
- Missing test: weak-signal scenario.

### G - Backend/API inacessivel

- Success exit: wait/error public state.
- Error exit: black wait.
- Max no-feedback: 5s.
- Expected screen: waiting_for_api.
- Recovery: cache/retry/error.
- Existing test: C15.3.2 bridge.
- Missing test: API outage simulation.

### H - Configuracao concluida

- Success exit: player starts.
- Error exit: no confirmation.
- Max no-feedback: 3s.
- Expected screen: saving/player.
- Recovery: error if writer fails.
- Existing test: C15.2.4.
- Missing test: camera timing.

### I - Espera por conteudo/cache/API

- Success exit: loading_content visible.
- Error exit: black screen.
- Max no-feedback: 5s.
- Expected screen: loading_content.
- Recovery: retry/error_no_content.
- Existing test: C15.3.2.
- Missing test: first-frame HDMI validation.

### J - Player normal

- Success exit: content plays.
- Error exit: loop/black failure.
- Max no-feedback: 10s.
- Expected screen: playing.
- Recovery: status/restart.
- Existing test: C15.2.4/C15.3.2.
- Missing test: C18 timing/sync audit.

### K - Midia indisponivel

- Success exit: friendly error/fallback.
- Error exit: black screen.
- Max no-feedback: 5s.
- Expected screen: error_no_content.
- Recovery: support/retry.
- Existing test: partial status bridge.
- Missing test: missing-media scenario.

### L - Reabrir configuracao

- Success exit: wizard opens/restores player.
- Error exit: echo/config race.
- Max no-feedback: 3s.
- Expected screen: open_settings/setup.
- Recovery: cancel restores.
- Existing test: C15.1.3/C15.2.4.
- Missing test: regression battery.

### M - Update remoto

- Success exit: update status safe.
- Error exit: unknown update state.
- Max no-feedback: 10s.
- Expected screen: update_checking/applying.
- Recovery: rollback/status.
- Existing test: C14 updater.
- Missing test: update UX scenario.

### N - Falha de update

- Success exit: old version preserved.
- Error exit: user thinks broken.
- Max no-feedback: 5s.
- Expected screen: update_failed.
- Recovery: retry/support.
- Existing test: C14 rollback scripts.
- Missing test: failure UX test.

### O - Reboot controlado

- Success exit: boot to player/config.
- Error exit: long black screen.
- Max no-feedback: 3s.
- Expected screen: boot/preparing/player.
- Recovery: support if no return.
- Existing test: C15.1.3.
- Missing test: C17 clean reboot pass.

### P - Recuperacao pos-falha

- Success exit: safe action clear.
- Error exit: physical cut confused with test.
- Max no-feedback: 5s.
- Expected screen: support/maintenance.
- Recovery: sanitized probes.
- Existing test: C15.2.3.
- Missing test: runbook UX validation.

### Q - Suporte remoto

- Success exit: public status sufficient.
- Error exit: secrets/raw logs.
- Max no-feedback: 10s.
- Expected screen: maintenance/support.
- Recovery: temporary probes.
- Existing test: C15/C14 probes.
- Missing test: status schema audit.

### R - Estado sem internet

- Success exit: cache or clear error.
- Error exit: black screen.
- Max no-feedback: 5s.
- Expected screen: waiting_for_api/offline.
- Recovery: reconnect/configure.
- Existing test: offline-first tests.
- Missing test: board offline UX.

### S - Estado com cache existente

- Success exit: cached content or wait shown.
- Error exit: API/cache ambiguity.
- Max no-feedback: 5s.
- Expected screen: loading_content/playing.
- Recovery: use cache.
- Existing test: player cache tests.
- Missing test: visual cache scenario.

### T - Estado sem cache

- Success exit: no-content error.
- Error exit: indefinite black.
- Max no-feedback: 5s.
- Expected screen: error_no_content.
- Recovery: network/API support.
- Existing test: partial.
- Missing test: no-cache negative test.

## Rules

- Critical waits get feedback within the listed max no-feedback window.
- If HDMI/camera is required, SSH-only validation is not enough for final
  perception.
- If a journey can be update-remote tested, prefer that before image rebuild.
- If a journey requires image boot, it belongs in C17 validation.
