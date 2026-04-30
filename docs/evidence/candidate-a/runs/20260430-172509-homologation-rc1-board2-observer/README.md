# Homologacao v0.1-rc1 - board 2 observer

Data: 2026-04-30

## Objetivo

Provisionar a placa de homologacao v0.1-rc1, sem ativar `systemd` da
aplicacao, e rodar o observer de 300 segundos com a configuracao candidata.

Placa: homologacao, IP redigido.

Cartao: H2testw aprovado pelo operador.

Imagem base:

```text
Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58_minimal.img
```

Paths reais, URLs privadas, API keys, identificadores privados, nomes privados
e payloads privados nao foram publicados.

## Checkouts

- `orange_pi_totem`: `ac913a0 Documenta homologacao v0.1-rc1`
- `kiosky-player`: `c71318a Add configurable MPV output flags`
- Branch do app: `appliance-v0.1`

O checkout do app contem suporte a:

- `mpv_query_uses_fresh_ipc`
- `mpv_vo`
- `mpv_gpu_context`
- `mpv_ao`

## Provisionamento

Scripts executados na placa de homologacao:

- `scripts/board/collect_diag.sh`
- `scripts/board/setup_data_layout.sh`
- `scripts/board/setup_totem_user.sh`
- `scripts/board/setup_app_dirs.sh`
- `scripts/board/setup_totem_media_groups.sh`
- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/disable_bluetooth.sh`
- `scripts/board/check_app_prereqs.sh`
- `scripts/board/kiosky_playback_observer_probe.sh`
- `scripts/board/collect_diag.sh`

Runtime instalado/confirmado:

- `mpv`: OK
- `ffmpeg`: OK
- `python3`: OK
- `python3-requests`: OK
- `python3-pip`: nao instalado
- `python3-venv`: pacote nao instalado

`apt update` foi executado. A instalacao foi simulada antes de instalar o
runtime minimo; a simulacao indicou `0` removidos e nenhum pacote critico de
kernel/Armbian em atualizacao.

Servicos Bluetooth/AW859A:

- `bluetooth.service`: desabilitado
- `aw859a-bluetooth.service`: desabilitado

Aplicacao:

- Deploy em `/opt/totem/kiosky-player`: OK
- Config privada fora do checkout: OK
- `systemd` da aplicacao: nao ativado

## Config candidata confirmada

A config privada foi copiada para `/data/config/config.json` sem imprimir o
conteudo. Somente campos nao sensiveis foram validados.

| Campo | Valor esperado | Status |
| --- | --- | --- |
| `mpv_query_uses_fresh_ipc` | `true` | OK |
| `mpv_vo` | `gpu` | OK |
| `mpv_gpu_context` | `drm` | OK |
| `mpv_ao` | `null` | OK |
| `low_resource_mode` | `false` | OK |
| `watchdog_interval_sec` | `10` | OK |
| `mpv_watchdog_ping_failures_before_restart` | `2` | OK |
| `mpv_watchdog_grace_after_load_sec` | `0` | OK |
| `mpv_watchdog_grace_after_restart_sec` | `0` | OK |
| `mpv_ipc_timeout_sec` | `2.0` | OK |
| `mpv_startup_timeout_sec` | `10.0` | OK |
| `hwdec` | `auto-safe` | OK |
| `mpv_log_file` | `/tmp/kiosky/mpv.log` | OK |
| `mpv_msg_level` | `all=v` | OK |
| `mpv_debug_events` | `true` | OK |
| owner/mode | `root:totem`, `0640` | OK |

O log MPV confirmou a presenca de:

```text
--vo=gpu --gpu-context=drm --ao=null
```

## Artefatos

Artefatos brutos copiados para esta pasta:

- `kiosky-playback-observer-20260430-171951-0300.tar.gz`
- `totem-diag-20260430-171407-0300.tar.gz`
- `totem-diag-20260430-172459-0300.tar.gz`

Os conteudos extraidos foram analisados localmente em `extracted/`, que deve
permanecer ignorado pelo Git.

## check_app_prereqs

Resultado: passou.

Avisos observados:

- `pip` ausente: esperado para a RC1.
- `/opt/totem/venv` existe, mas nao possui binarios preparados: esperado nesta
  RC1, que nao usa `pip`/`venv`.

## Observer 300s

`app-run`:

- Exit code: `124`
- Interpretacao: timeout esperado do probe de 300 segundos.
- `app-run.stderr.txt`: 0 linhas.
- `app-run.stdout.txt`: 212 linhas.

Status final sanitizado:

- `playback_state=playing`
- `playlist_size=15`
- `current_index=9`
- `mpv_running=true`
- `consecutive_failures=0`
- `blocked_media_count=0`
- `last_poll_error=null`
- `last_render_error=null`
- `black_screen_risk_reason=null`

Metricas do app:

| Metrica | Valor |
| --- | ---: |
| `MPV IPC command timeout` | 0 |
| `MPV IPC ping failed` | 0 |
| `Restarting MPV` | 0 |
| `MPV process started` | 1 |
| `Failed to load media` | 0 |
| `MPV loadfile returned error` | 0 |
| `Media load retry failed` | 0 |
| `Bad file descriptor` | 0 |
| `MPV process exited unexpectedly` | 0 |
| `Playing media` | 25 |

Observador externo:

| Metrica | Valor |
| --- | ---: |
| Amostras totais | 289 |
| IPC success | 281 |
| IPC timeout | 6 |
| IPC error | 2 |
| `missing_socket` | 2 |
| `partial_response` | 6 |
| Aliases unicos observados | 15 |

Resultado de progressao por alias:

- Aliases com amostras numericas de `time-pos` e `estimated-frame-number`: `0`.
- Aliases comprovadamente avancando `time-pos` e `estimated-frame-number`: `0/15`.
- Motivo observado: o MPV retornou `property unavailable` para `time-pos` e
  `estimated-frame-number` nas amostras do observador externo.

Essa lacuna impede aprovar integralmente a rodada pelos criterios definidos,
apesar de os contadores internos do app estarem limpos.

## Systemd, kernel e processos

`systemctl --failed` apos o observer:

```text
0 loaded units listed.
```

Filtro critico de kernel apos o observer:

- Sem `Oops`.
- Sem `panic`.
- Sem erro EXT4.
- Sem remount read-only.
- Sem `mmc timeout/reset`.
- Sem eventos no filtro critico usado pela rodada.

Escrita em `/opt`:

- `post-opt-newer-marker`: vazio.

Processos remanescentes:

- `post-processes-totem`: vazio.
- `post-processes-all`: apenas o proprio comando de busca.
- Sem processo real remanescente de `kiosk.py` ou `mpv`.

## Observacao humana

Observacao humana de tela: pendente.

## Conclusao

Bloqueado para aprovacao integral do observer de homologacao v0.1-rc1 na
segunda placa.

O provisionamento base foi concluido, o app rodou por 300 segundos sem falhas
internas de IPC/watchdog/loadfile, sem falhas systemd, sem eventos criticos de
kernel, sem escrita em `/opt` e sem processos remanescentes. Porem, o observer
externo nao comprovou progressao de `time-pos` e `estimated-frame-number`, que
e criterio obrigatorio de aprovacao.

## Proximo passo recomendado

1. Revisar a instrumentacao do observer para entender por que o MPV retornou
   `property unavailable` para `time-pos` e `estimated-frame-number` nesta
   placa/rodada.
2. Repetir o observer de 300 segundos com comprovacao de progressao por alias,
   mantendo a mesma config candidata.
3. Depois de passar, executar o teste manual de 30-60 minutos.
4. Somente depois validar `systemd` da aplicacao de forma controlada.
