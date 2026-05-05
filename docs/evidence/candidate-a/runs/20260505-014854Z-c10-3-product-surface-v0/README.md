# C10.3 Product Surface V0 - Validacao Humana

Data: 2026-05-05

HEAD durante a validacao: `005a350`

## Comandos

- `scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --prepare-only`
- `scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --preview-wizard`
- `scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --run-wifi-list-preview`
- `scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --run-cancel`
- `scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --run-complete-existing-wifi`
- `scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --apply-boot-visual-guardrails`
- `scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --reboot-visual-check`

## Resultado

- prepare-only: passou;
- preview do wizard: passou;
- preview de lista Wi-Fi: passou;
- cancelamento: passou;
- conclusao com Wi-Fi dedicado existente: passou;
- candidata gerada: true;
- C5.1 allow-mock: passou;
- C5.1 real-dry-run: falhou como esperado por placeholders;
- orientacao escolhida: retrato para direita;
- rotation_deg registrado: 90;
- lista Wi-Fi local: exibida somente no HDMI;
- wifi_networks_found_count: 7;
- selected_network_present: true;
- selected_network_signal_bucket: strong;
- selected_network_security_present: true;
- boot_visual_guardrails_applied: true;
- rollback_state_present: true;
- reboot_visual_check: true;

## Estado Final

- SSH voltou: true;
- servico final: active/enabled;
- NRestarts: 0;
- public_state: player_running;
- playback: playing;
- player: 1;
- MPV: 1;
- renderer: 0 depois de convergencia tardia;
- setup: 0;
- systemctl_failed_count: 0;

## Guardrails

- real_config_read: false;
- real_config_written: false;
- writer_called: false;
- wifi_changed: false;
- network_changed nos previews/listagem: false;
- hotspot_created: false;
- portal_created: false;
- root_read_only_enabled: false;
- power_cut_tested: false;

## Observacao

O primeiro `--reboot-visual-check` foi interrompido porque a espera de SSH do
runner usava autenticacao em lote, inadequada para o acesso por senha. Um
snapshot sanitizado manual confirmou retorno do SSH e estado final correto. O
runner foi ajustado para detectar retorno por TCP/22 antes do SSH final.

## Nao Publicado

- SSID real;
- senha;
- IP;
- MAC;
- BSSID;
- gateway;
- DNS;
- hostname;
- api_key;
- api_url real;
- environment_id real;
- config real;
- backup;
- logs brutos.
