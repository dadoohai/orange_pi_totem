# Teste manual controlado do kiosky-player

## Objetivo

Preparar o primeiro run manual supervisionado do `kiosky-player` na Orange Pi Zero 3 Candidato A, usando o runtime minimo ja validado e preservando DRM/KMS como caminho principal de display.

Esta etapa nao ativa systemd, nao instala pacotes e nao deve copiar config privada para o Git.

## Pre-requisitos

- Candidato A em `foundation-v0.1`.
- `kiosky-player` local em `appliance-v0.1`, com checkout revisado.
- Codigo do app copiado para `/opt/totem/kiosky-player` via `scripts/remote/deploy_kiosky_player.sh`.
- `mpv`, `ffmpeg` e `python3-requests` ja instalados na imagem.
- `python3-pip`, `python3-venv`, Xorg, Wayland, compositor e Chromium continuam fora desta fase.
- MPV manual via DRM/KMS aprovado como root e como usuario `totem`, com confirmacao visual HDMI.
- Usuario `totem` nos grupos `audio`, `video` e `render`.
- Diretorios persistentes existentes:
  - `/data/config`
  - `/data/media/kiosky-player`
  - `/data/state/kiosky-player`
  - `/data/spool/kiosky-player`
  - `/data/logs/kiosky-player`
- `/tmp/kiosky` criado como `totem:totem`, modo `0750`.
- `systemctl --failed` sem unidades falhadas relevantes.

## Config privada

Criar `/data/config/config.json` manualmente na placa, fora do Git e fora do checkout do app. Nao copiar `config.json` real do repositorio local.

Exemplo de fluxo manual na placa:

```bash
install -d -m 0750 -o totem -g totem /data/config
umask 077
cat >/data/config/config.json <<'JSON'
{
  "api_url": "https://api.example.invalid/search",
  "api_key": "replace-with-real-api-key",
  "environment_id": "replace-with-real-environment-id",
  "station_id": "replace-with-station-id",
  "only_standby": true,
  "search_in": "campaign",
  "include_descendants": true,
  "limit": 20,
  "poll_interval_sec": 1800,
  "request_timeout_sec": 15,
  "default_duration_ms": 10000,
  "cache_dir": "/data/media/kiosky-player",
  "state_dir": "/data/state/kiosky-player",
  "offline_fallback": true,
  "offline_max_age_hours": 0,
  "offline_ignore_max_age_when_no_network": true,
  "require_full_download_before_switch": true,
  "allow_empty_playlist_from_api": false,
  "disable_cleanup_when_offline": true,
  "cache_max_files": 200,
  "cache_max_bytes": 2147483648,
  "min_free_space_bytes": 536870912,
  "max_download_bytes": 536870912,
  "mpv_path": "mpv",
  "ipc_path": "/tmp/kiosky/mpv.sock",
  "runtime_dir": "/tmp/kiosky",
  "strict_paths_enabled": true,
  "rotation_deg": 0,
  "hotkeys_enabled": false,
  "hotkey_open_key": "Ctrl+s",
  "config_ui_enabled": false,
  "config_ui_bind": "127.0.0.1",
  "config_ui_port": 8765,
  "low_resource_mode": true,
  "telemetry_enabled": false,
  "telemetry_url": "https://telemetry.example.invalid/telemetry",
  "telemetry_token": "",
  "telemetry_interval_sec": 60,
  "telemetry_timeout_sec": 10,
  "preload_next": false,
  "mute": false,
  "lock_input": true,
  "hwdec": "auto-safe",
  "log_file": "",
  "log_max_bytes": 5000000,
  "log_backup_count": 3,
  "watchdog_interval_sec": 10,
  "media_load_retry_cooldown_sec": 60,
  "tmp_max_age_sec": 3600,
  "status_file": "/tmp/kiosky-status.json",
  "status_interval_sec": 5,
  "cleanup_interval_sec": 1800,
  "sync_enabled": false,
  "sync_drift_threshold_ms": 300,
  "sync_hard_resync_ms": 1200,
  "sync_boot_hard_check_sec": 300,
  "sync_checkpoint_interval_sec": 3600,
  "sync_prep_mode": "play_then_resync",
  "sync_ntp_command": ""
}
JSON
chown root:totem /data/config/config.json
chmod 0640 /data/config/config.json
```

Substituir os placeholders por valores reais apenas na placa:

- `api_url`
- `api_key`
- `environment_id`
- `station_id`

Manter os caminhos appliance:

- `cache_dir`: `/data/media/kiosky-player`
- `state_dir`: `/data/state/kiosky-player`
- `status_file`: `/tmp/kiosky-status.json`
- `ipc_path`: `/tmp/kiosky/mpv.sock`
- `runtime_dir`: `/tmp/kiosky`
- `strict_paths_enabled`: `true`

Nao registrar `api_key`, `environment_id`, `station_id`, URLs privadas, nomes de campanha ou payloads da API em README publico. Artefatos brutos podem conter dados sensiveis e nao devem ser commitados.

## Probe manual

Depois que a config privada existir na placa, executar:

```bash
./scripts/remote/push_and_run.sh root@192.168.1.147 scripts/board/kiosky_manual_probe.sh
```

O probe:

- exige `/data/config/config.json`;
- nao imprime o conteudo da config;
- nao imprime `api_key`;
- recria `/tmp/kiosky` como `totem:totem`, modo `0750`, se necessario;
- executa o app como usuario `totem`;
- usa timeout de 300 segundos;
- usa `PYTHONDONTWRITEBYTECODE=1` e `XDG_RUNTIME_DIR=/tmp/kiosky`;
- captura stdout/stderr em `/root/totem-diag/kiosky-manual-<timestamp>/`;
- gera `/root/totem-diag/kiosky-manual-<timestamp>.tar.gz`;
- verifica se houve escrita em `/opt/totem/kiosky-player` apos um marcador criado antes do run;
- copia `/tmp/kiosky-status.json` para o artefato bruto se existir, sem imprimir seu conteudo.

Comando base usado pelo probe:

```bash
runuser -u totem -- env PYTHONDONTWRITEBYTECODE=1 XDG_RUNTIME_DIR=/tmp/kiosky timeout 300s python3 /opt/totem/kiosky-player/kiosk.py --config /data/config/config.json
```

## Coleta de artefatos

Depois do probe, criar uma rodada em `docs/evidence/candidate-a/runs/` e puxar os artefatos:

```bash
RUN_DIR="docs/evidence/candidate-a/runs/$(date +%Y%m%d-%H%M%S)-kiosky-manual-probe"
mkdir -p "$RUN_DIR"
./scripts/remote/pull_artifacts.sh root@192.168.1.147 "$RUN_DIR" "kiosky-manual-*.tar.gz"
./scripts/remote/pull_artifacts.sh root@192.168.1.147 "$RUN_DIR" "totem-diag-*.tar.gz"
```

Criar um `README.md` sanitizado para a rodada. Nao commitar `.tar.gz` brutos.

## Criterios de aprovacao

- O probe roda com `/data/config/config.json` presente e legivel pelo usuario `totem`.
- O app inicia como usuario `totem`.
- MPV e exibicao HDMI funcionam durante a janela do teste.
- O app nao escreve em `/opt/totem/kiosky-player` apos o marcador.
- Escritas ficam restritas a `/data` e `/tmp`.
- `/tmp/kiosky-status.json`, se existir, indica estado coerente para o teste.
- `systemctl --failed` permanece sem unidades falhadas relevantes.
- Sem `Oops`, `panic`, erro EXT4, remount read-only, `mmc timeout/reset` ou alerta de voltage no filtro critico do kernel.
- Nenhum pacote e instalado.
- Nenhum servico systemd da aplicacao e instalado, habilitado ou iniciado.

Exit code `124` do comando do app pode significar somente que o timeout de 300 segundos encerrou o teste. Interpretar junto com stdout/stderr, status JSON, display e logs de kernel.

## Criterios de bloqueio

- Config ausente, ilegivel por `totem`, com placeholders ou com JSON invalido.
- `api_key` ou outro segredo aparece em stdout/stderr, README ou arquivo versionado.
- `requests` indisponivel.
- MPV nao inicia ou nao exibe conteudo no HDMI.
- O app grava arquivos em `/opt/totem/kiosky-player`.
- `systemctl --failed` passa a listar falha relevante.
- Kernel registra `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`.
- O teste exige instalar Xorg, Wayland, compositor ou Chromium antes de explicar a falha atual.

## Escopo negativo

Nesta etapa ainda nao executar:

- `apt install`, `apt upgrade`, `apt full-upgrade`, `apt dist-upgrade` ou `armbian-upgrade`;
- instalacao de `python3-pip` ou `python3-venv`;
- instalacao de Xorg, Wayland, compositor ou Chromium;
- `systemctl enable` ou `systemctl start` da aplicacao;
- deploy de config real a partir do repositorio;
- commit de artefatos `.tar.gz`, config privada ou secrets.
