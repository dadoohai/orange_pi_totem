# C10.7.2 - Operational Clean State + Reproducibility Refresh

Data: 2026-05-05

Escopo: refresh curto para devolver a placa dev a estado operacional limpo apos
C10.6.2/C10.7.1, corrigir limpeza/diagnostico do fluxo F10 e rerodar a
auditoria C10.7. Nao foi usado segundo cartao/placa.

## Git

- branch: `foundation-v0.1`
- HEAD inicial/final do runner: `c87c9a0a3a9434a8b58ba945cfdbee963e4da7e2`
- C10.6.2 presente no historico: `ede0fbc Add C10.6.2 F10 settings apply flow`
- C10.7 presente no historico: `4d65f28 Add C10.7 reproducibility audit`
- C10.7.1 presente no historico: `c87c9a0 Add C10.7.1 reproducibility refresh`
- worktree inicial: limpo
- worktree durante o runner final: 2 arquivos dirty, ambos de C10.7.2:
  `scripts/board/totem_open_settings_session.sh` e
  `scripts/board/totem_settings_trigger.py`

## Preflight Inicial

Estado sanitizado observado antes da limpeza:

- `totem-open-settings.service=activating/static`
- `kiosky-player.service=inactive/enabled`
- `totem-settings-trigger.service=active/enabled`
- processo de setup presente
- `session.lock=true`
- `request.json=true`
- `public_state=maintenance_placeholder`
- playback publico `playing`
- `systemctl_failed_count=0`

Classificacao: `stale_session_suspected`.

## Limpeza Segura

Acao executada na placa:

- parado apenas `totem-open-settings.service`;
- removidos somente arquivos temporarios/stale em `/run/dadooh-settings`;
- restaurado `kiosky-player.service`;
- resetado estado failed residual da unit de open-settings apos o stop;
- preservados config real, Wi-Fi, writer, pacotes, reboot, player/kiosky-player
  e segunda placa.

## Correcao Versionada

Arquivos alterados no repo e reinstalados em `/opt/totem/bin` na placa:

- `scripts/board/totem_open_settings_session.sh`
- `scripts/board/totem_settings_trigger.py`

Mudancas:

- `totem_open_settings_session.sh` remove `request.json` no fechamento normal e
  no `trap`;
- `totem_settings_trigger.py` registra diagnostico sanitizado quando existe
  lock ativo: `session_lock_age_bucket`, `open_service_active_state` e
  `stale_lock_suspected`;
- o trigger continua bloqueando nova sessao enquanto `session.lock` existir.

Somente `totem-settings-trigger.service` foi reiniciado para carregar o novo
trigger. `kiosky-player.service` nao foi reinstalado nem modificado em disco.

## Estado Final

- `clean_operational_state=true`
- `session_lock_present=false`
- `request_file_present=false`
- `open_settings_service_state=inactive/static`
- `player_service_state=active/enabled`
- `trigger_service_state=active/enabled`
- `systemctl_failed_count=0`
- `setup_process_count=0`
- `public_state=player_running`
- `playback=playing`
- `mpv_running=true`
- `orientation_json_present=true`
- `orientation_json_mode=0644`
- `orientation_json_schema=dadooh-display-orientation.v1`
- `orientation_rotation_deg=270`
- `orientation_label=portrait_left`
- `ready_for_c10_8_installer=true`
- `second_board_ready_by_script_today=false`

## Auditoria C10.7

Artefatos sanitizados locais:

```text
/tmp/dadooh-c10-7-reproducibility-audit/20260505T160644Z-c10-7-2-reproducibility-clean-state/
```

Resumo do runner:

- repo_branch: `foundation-v0.1`
- repo_dirty_entries: `2`
- systemctl_failed_count: `0`
- public_state: `player_running`
- playback: `playing`
- fully_reproducible_today: `false`
- second_board_ready_by_script_today: `false`

Bloqueios restantes antes da segunda placa:

- falta C10.8, instalador idempotente unico do appliance;
- falta pin/manifest explicito do `kiosky-player`;
- `dadooh-visual-splash.service` existe na placa, mas ainda precisa ser
  versionado como unit standalone ou gerado deterministicamente;
- `/opt/totem/bin` ainda precisa ser reinstalado a partir de um commit unico e
  validado por manifest.

## Checks

```bash
git status --short
git log --oneline -15
git branch --show-current
git rev-parse HEAD
git diff --check
bash -n scripts/board/totem_open_settings_session.sh
python3 scripts/board/totem_settings_trigger.py --self-test
ssh <host> '<preflight sanitizado C10.7.2>'
scp scripts/board/totem_open_settings_session.sh scripts/board/totem_settings_trigger.py <host>:/tmp/dadooh-c10-7-2-script-refresh/
ssh <host> '<instalar scripts F10 corrigidos e reiniciar apenas totem-settings-trigger.service>'
scripts/remote/run_c10_7_reproducibility_audit.sh <host> --summary --out-dir /tmp/dadooh-c10-7-reproducibility-audit/20260505T160644Z-c10-7-2-reproducibility-clean-state
ssh <host> '<preflight final sanitizado>'
```

Nao foi executado F10 cancel/dry-run nesta rodada depois da limpeza, para nao
abrir nova sessao interativa local apos estabilizar a placa. C10.8 deve incluir
smoke curto de F10 cancel/dry-run apos existir o instalador idempotente.

## Sanitizacao

Esta evidencia nao inclui config real, backup, candidata privada, payload,
logs brutos, IP, MAC, DNS, gateway, hostname, nome real de conexao, SSID, senha,
`api_url`, `api_key`, `environment_id` ou `station_id`.
