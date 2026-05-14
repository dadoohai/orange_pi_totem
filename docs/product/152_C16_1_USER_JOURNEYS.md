# 152 - C16.1 - User Journeys

## Scope

This map defines the critical journeys that future UI/UX QA must score. It is
also the checklist C17 should use when validating the next consolidated image.

| ID | Journey | Success exit | Error exit | Max no-feedback | Expected screen | Recovery | Existing test | Missing test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | Primeira energizacao | feedback inicial appears | black screen prolonged | 3s | boot | support checks boot/power | C15 splash validations | HDMI/camera timing |
| B | Boot sem configuracao | config pending visible | login/terminal visible | 3s | config_pending | press F10/support | C15.2.4 clean-board | camera flicker check |
| C | Primeira configuracao via F10 | config written/player restored | wizard exits alone | 5s | wizard | back/cancel/retry | C15.2.4 full setup | synthetic journey runner |
| D | Selecao de Wi-Fi | network selected | list confusing | 10s | wifi_list | R refresh/Esc | C15.1.4 | offline visual regression |
| E | Senha Wi-Fi errada | user can retry | technical failure | 5s | wifi_password_error | retry/back | partial | negative board test |
| F | Wi-Fi fraco/instavel | signal risk visible | unexplained drop | 10s | wifi_list | choose stronger network | C15.1.4 labels | weak-signal scenario |
| G | Backend/API inacessivel | wait/error public state | black wait | 5s | waiting_for_api | cache/retry/error | C15.3.2 bridge | API outage simulation |
| H | Configuracao concluida | player starts | no confirmation | 3s | saving/player | error if writer fails | C15.2.4 | camera timing |
| I | Espera por conteudo/cache/API | loading_content visible | black screen | 5s | loading_content | retry/error_no_content | C15.3.2 | first-frame HDMI validation |
| J | Player normal | content plays | loop/black failure | 10s | playing | status/restart | C15.2.4/C15.3.2 | C18 timing/sync audit |
| K | Midia indisponivel | friendly error/fallback | black screen | 5s | error_no_content | support/retry | partial status bridge | missing-media scenario |
| L | Reabrir configuracao | wizard opens/restores player | echo/config race | 3s | open_settings/setup | cancel restores | C15.1.3/C15.2.4 | regression battery |
| M | Update remoto | update status safe | unknown update state | 10s | update_checking/applying | rollback/status | C14 updater | update UX scenario |
| N | Falha de update | old version preserved | user thinks broken | 5s | update_failed | retry/support | C14 rollback scripts | failure UX test |
| O | Reboot controlado | boot to player/config | long black screen | 3s | boot/preparing/player | support if no return | C15.1.3 | C17 clean reboot pass |
| P | Recuperacao pos-falha | safe action clear | physical cut confused with test | 5s | support/maintenance | sanitized probes | C15.2.3 | runbook UX validation |
| Q | Suporte remoto | public status sufficient | secrets/raw logs | 10s | maintenance/support | temporary probes | C15/C14 probes | status schema audit |
| R | Estado sem internet | cache or clear error | black screen | 5s | waiting_for_api/offline | reconnect/configure | offline-first tests | board offline UX |
| S | Estado com cache existente | cached content or wait shown | API/cache ambiguity | 5s | loading_content/playing | use cache | player cache tests | visual cache scenario |
| T | Estado sem cache | no-content error | indefinite black | 5s | error_no_content | network/API support | partial | no-cache negative test |

## Rules

- Critical waits get feedback within the listed max no-feedback window.
- If HDMI/camera is required, SSH-only validation is not enough for final
  perception.
- If a journey can be update-remote tested, prefer that before image rebuild.
- If a journey requires image boot, it belongs in C17 validation.
