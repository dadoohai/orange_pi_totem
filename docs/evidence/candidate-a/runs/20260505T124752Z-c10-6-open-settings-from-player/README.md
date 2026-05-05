# C10.6 - Abrir Configuracoes com player rodando

Data: 2026-05-05

Commit base: `62a98ec`

## Comandos executados

- `scripts/remote/run_c10_6_open_settings_from_player.sh <host> --prepare-only`
- `scripts/remote/run_c10_6_open_settings_from_player.sh <host> --preview-open-settings`
- `scripts/remote/run_c10_6_open_settings_from_player.sh <host> --run-open-cancel`
- `scripts/remote/run_c10_6_open_settings_from_player.sh <host> --run-trigger-local-human --trigger-timeout-sec 180`

## Resultado

- `trigger_type`: `keyboard_ctrl_i_hold` ou `keyboard_f10_hold`
- `trigger_detected`: true
- `open_settings_result`: wizard visual aberto diretamente
- `cancel_result`: cancelled
- `dry_run_result`: not_run
- `writer_called`: false
- `real_config_read`: false
- `real_config_written`: false
- `wifi_changed`: false
- `networkmanager_changed`: false

## Estado final

- `service_final`: active/enabled
- `NRestarts`: 0
- `public_state`: player_running
- `playback`: playing
- `player`: 1
- `MPV`: 1
- `renderer`: 0
- `setup`: 0

## Guardrails

- Config real nao foi publicada.
- Candidata privada nao foi publicada.
- `api_key`, `api_url`, `environment_id`, SSID, senha, IP, MAC e DNS nao foram publicados.
- Logs brutos e teclas digitadas nao foram publicados.
- Menu de manutencao/suporte nao foi criado.
- Terminal/root nao aparecem na UI do operador.
