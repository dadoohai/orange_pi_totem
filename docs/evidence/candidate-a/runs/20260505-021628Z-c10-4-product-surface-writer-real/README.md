# C10.4 Product Surface Writer Real

Data: 2026-05-05

Commit base: `8c9fe6c`

## Comandos

```bash
scripts/remote/run_c10_4_product_surface_writer_real.sh <board-host> --prepare-only
scripts/remote/run_c10_4_product_surface_writer_real.sh <board-host> --preflight
scripts/remote/run_c10_4_product_surface_writer_real.sh <board-host> --run-dry-run --private-values-from-active-config
scripts/remote/run_c10_4_product_surface_writer_real.sh <board-host> --run-real-write-start --private-values-from-active-config
```

## Resultado

- `prepare-only`: passou;
- `preflight`: passou;
- `run-dry-run`: passou;
- `run-real-write-start`: passou;
- orientacao escolhida: `portrait_right`;
- `rotation_deg`: `90`;
- `network_step`: `existing_configured_wifi`;
- writer_called: `true`;
- writer_result: `passed`;
- real_config_written: `true`;
- backup_created: `true`;
- permissions_ok: `true`;
- totem_read_ok: `true`;
- totem_write_blocked: `true`;
- dedicated_wifi_profile_present: `true`;
- private_candidate_real_dry_run_passed: `true`;
- private_candidate_removed: `true`;
- private_source_temp_removed: `true`;
- service_active: `active`;
- service_enabled: `enabled`;
- NRestarts: `0`;
- public_state: `player_running`;
- playback: `playing`;
- player/MPV/renderer/setup: `1/1/0/0`;
- root_read_only_enabled: `false`;
- power_cut_tested: `false`;

## Nao Alterado

- Wi-Fi/NetworkManager nao foi alterado;
- hotspot nao foi criado;
- portal nao foi criado;
- repo `kiosky-player` nao foi alterado;
- root read-only nao foi habilitado;
- corte seco nao foi executado;
- reboot nao foi executado nesta rodada.

## Privacidade

Nao foram publicados config real, backup, candidata privada, endpoint privado,
credencial privada, identificador real de ambiente, SSID, senha, IP, MAC,
BSSID, gateway, DNS, hostname, UUID, caminhos privados, payloads ou logs brutos.
