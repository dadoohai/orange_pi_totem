# Systemd dev smoke - kiosky-player

Data: 2026-04-30

Placa: desenvolvimento, IP redigido.

## Objetivo

Validar o `kiosky-player` como servico `systemd` na placa de desenvolvimento, com start/stop controlado e sem habilitar boot automatico.

Esta rodada usa a configuracao candidata ja aprovada no observer manual:

- `mpv_query_uses_fresh_ipc=true`
- `mpv_vo=gpu`
- `mpv_gpu_context=drm`
- `mpv_ao=null`
- `low_resource_mode=false`
- `watchdog_interval_sec=10`
- `mpv_watchdog_ping_failures_before_restart=2`
- `mpv_watchdog_grace_after_load_sec=0`
- `mpv_watchdog_grace_after_restart_sec=0`
- `mpv_ipc_timeout_sec=2.0`
- `mpv_startup_timeout_sec=10.0`
- `hwdec=auto-safe`

Valores privados da config nao foram impressos.

## Escopo

- `kiosky-player`: `c71318a Add configurable MPV output flags`
- Unit instalada: `kiosky-player.service`
- `systemctl daemon-reload`: executado
- `systemctl enable`: nao executado
- Estado final de enable: `disabled`

A unit usada nesta rodada e a versao simples em `scripts/board/kiosky-player.service`: executa como `User=totem`, `Group=totem`, cria `/tmp/kiosky` antes do start, usa logs via journal e mantem `/opt/totem` somente leitura para o servico. As linhas de TTY testadas durante a investigacao foram revertidas, pois a falha inicial era HDMI desconectado e a unit simples passou apos conectar o display.

## Tentativa inicial sem HDMI

A primeira tentativa produziu artefatos, mas foi classificada como inconclusiva para o app:

- HDMI estava desconectado.
- O MPV registrou falhas de inicializacao KMS/GPU.
- O servico foi parado e nao ficou processo remanescente.

Essa fase serviu apenas para confirmar que o display fisico e requisito para esta validacao DRM/KMS.

## Smoke test pos-HDMI

Artefato: `kiosky-systemd-smoke-20260430-175509-0300.tar.gz`

| Item | Resultado |
| --- | --- |
| `systemctl start` | OK |
| Estado durante smoke | `active` |
| `systemctl is-enabled` | `disabled` |
| Status JSON | presente |
| `playback_state` | `playing` |
| `mpv_running` | `true` |
| Processo `python3` | 1 |
| Processo `mpv` | 1 |
| `systemctl --failed` | 0 units |
| Falha KMS/GPU no smoke pos-HDMI | 0 |
| Escrita em `/opt` apos marcador | 0 |
| `systemctl stop` | OK |
| Processos remanescentes apos stop | 0 |

O status final sanitizado nao indicou `last_poll_error`, `last_render_error`, `black_screen_risk_reason`, falhas consecutivas ou midias bloqueadas.

## Observer systemd de 10 minutos

Artefato: `kiosky-service-observer-20260430-175627-0300.tar.gz`

O observer nao iniciou o app; ele apenas observou o servico ja rodando e consultou o MPV por IPC curto independente.

| Metrica | Valor |
| --- | ---: |
| Amostras | 597 |
| IPC success | 597 |
| IPC timeout | 0 |
| IPC error | 0 |
| Aliases observados | 5 |
| MPV IPC command timeout | 0 |
| MPV IPC ping failed | 0 |
| MPV IPC ping ok | 60 |
| Restarting MPV | 0 |
| MPV process started durante observer | 0 |
| Failed to load media | 0 |
| MPV loadfile returned error | 0 |
| `--vo=gpu` no log MPV | 1 |
| `--gpu-context=drm` no log MPV | 1 |
| `--ao=null` no log MPV | 1 |
| Falha KMS/GPU no log MPV | 0 |

Tabela por alias sanitizado:

| Alias | Duracao configurada (ms) | Duracao MPV (s) | `time-pos` min | `time-pos` max | `time-pos` avancou? | Frame min | Frame max | Frame avancou? | Pause? | Idle? | EOF? | Amostras |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- | --- | ---: |
| `<media-path:89207012a7>` | 7000 | 16.064218 | 0.000000 | 6.800000 | Sim | 0 | 204 | Sim | Nao | Nao | Nao | 89 |
| `<media-path:8f9272521c>` | 8600 | 8.568186 | 0.000000 | 8.458333 | Sim | 0 | 202 | Sim | Nao | Nao | Nao | 113 |
| `<media-path:c406539999>` | 15100 | 15.069751 | 0.000000 | 14.866667 | Sim | 0 | 446 | Sim | Nao | Nao | Nao | 196 |
| `<media-path:e7efe47f02>` | 10000 | 10.000000 | 0.066667 | 9.833333 | Sim | 2 | 295 | Sim | Nao | Nao | Nao | 130 |
| `<media-path:fece6ae2c0>` | 5100 | 5.131610 | 0.000000 | 4.916667 | Sim | 0 | 118 | Sim | Nao | Nao | Nao | 69 |

## Diagnostico final

- `systemctl --failed`: 0 units.
- `journalctl -k -p crit`: sem entradas.
- Filtro critico de kernel: apenas ruido de boot conhecido; sem Oops, panic, erro EXT4, remount read-only ou timeout/reset de MMC.
- Escrita em `/opt/totem/kiosky-player` apos marcador: 0 linhas.
- Processos `kiosk.py`/`mpv` remanescentes apos stop: 0. A unica linha em `post-processes-all` e o proprio comando de verificacao `pgrep`.

## Conclusao

Aprovado para uso controlado via `systemctl start/stop` na placa de desenvolvimento, com HDMI conectado. O servico nao foi habilitado no boot.

O bloqueio inicial era ambiental: sem HDMI conectado, o MPV nao conseguiu inicializar DRM/KMS. Apos conectar HDMI, a unit simples funcionou; as linhas adicionais de TTY nao foram necessarias e foram removidas.

## Proximo passo recomendado

Rodar um teste manual mais longo com o servico `systemd` na placa de desenvolvimento, ainda sem `enable`. Se passar sem regressao de IPC, loadfile, kernel, escrita em `/opt` ou processo remanescente, preparar a rodada separada para validar boot automatico.
