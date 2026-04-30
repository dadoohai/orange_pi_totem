# Homologacao v0.1-rc1

Status: versao de homologacao, nao producao.

Esta release congela um ponto reproduzivel para testar a configuracao candidata
em uma segunda Orange Pi Zero 3 e em outro cartao microSD. Ela nao libera
instalacao em campo, corte seco, root read-only nem `systemd` da aplicacao.

## Objetivo

Reproduzir em uma segunda placa/cartao a combinacao que passou no observer de
300s do app real em 2026-04-30:

- base Armbian Candidato A;
- runtime minimo sem desktop;
- `kiosky-player` em commit conhecido;
- config privada sanitizada neste documento;
- execucao manual do app, ainda sem unit `systemd`.

O objetivo e validar reprodutibilidade em hardware/cartao adicional antes de
continuar o desenvolvimento na placa atual.

## Historico macro

1. A imagem clonada antiga foi descartada como base de producao por conter
   estado manual, logs, possiveis corrupcoes e identificadores locais.
2. O cartao atual passou no H2testw, removendo a suspeita imediata de cartao
   falso ou claramente defeituoso.
3. A base foi reconstruida com Armbian Build v25.11, Debian Bookworm Minimal,
   kernel `6.12.58-current-sunxi64`, U-Boot `2025.04`, NetworkManager e
   `BSPFREEZE=yes`.
4. O Candidato A passou por boot inicial, reboots curtos, baseline de rede,
   stress leve CPU/RAM de 30 minutos, layout `/data`, Wi-Fi cliente 5 GHz,
   desativacao de `bluetooth.service` e `aw859a-bluetooth.service`.
5. O runtime minimo foi instalado de forma controlada: `mpv`, `ffmpeg` e
   `python3-requests`, sem `python3-pip`, sem `python3-venv`, sem Xorg, sem
   Wayland, sem compositor e sem Chromium.
6. O MPV manual via DRM/KMS foi aprovado como root e como usuario `totem`.
7. O `kiosky-player` passou a rodar manualmente como `totem`, usando config
   privada em `/data/config/config.json` e dados mutaveis em `/data`.
8. As rodadas de app isolaram primeiro o problema de IPC/watchdog; depois
   `mpv_query_uses_fresh_ipc=true` estabilizou IPC, ping, restart e `loadfile`.
9. O observer mostrou que alguns aliases nao avancavam tempo/frame ate a saida
   MPV ser explicitada com `--vo=gpu --gpu-context=drm --ao=null`.
10. A rodada `20260430-133130` aprovou a configuracao candidata por 300s no app
    real, ainda sem observacao humana direta e sem `systemd`.

## Composicao da base

| Item | Valor |
| --- | --- |
| Build | Armbian Build v25.11 |
| Distribuicao | Debian Bookworm Minimal |
| Kernel | `6.12.58-current-sunxi64` |
| U-Boot | `2025.04` |
| Rede | NetworkManager |
| Desktop | ausente |
| Congelamento | `BSPFREEZE=yes` |

Imagem base usada:

```text
Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58_minimal.img
```

Checksum SHA256 registrado na geracao:

```text
99fce7ad04f9c6529655d2d6f8568d5a484c05bdcbdf679e3423a5e7241894e7
```

## Geracao da imagem base

A imagem foi gerada em ambiente WSL2 com Ubuntu 24.04 e Docker, usando Armbian
Build v25.11 no commit `e172058`. Os parametros relevantes foram:

```text
BOARD=orangepizero3
RELEASE=bookworm
BRANCH=current
BUILD_MINIMAL=yes
BUILD_DESKTOP=no
KERNEL_CONFIGURE=no
NETWORKING_STACK=network-manager
BSPFREEZE=yes
```

O fluxo de gravacao foi feito fora do WSL, com ferramenta visual no Windows,
para reduzir risco operacional com device paths. O primeiro boot confirmou
kernel, `/etc/armbian-release`, pacotes criticos em hold e root expandido.

## Gravacao e teste do cartao

Para a segunda placa/cartao, o fluxo esperado e:

1. Testar o cartao completo com H2testw e registrar o resultado.
2. Gravar a imagem base `Armbian-unofficial_25.11.1_...minimal.img`.
3. Fazer primeiro boot supervisionado.
4. Validar rede e SSH como canal de bancada, sem publicar IPs, hostnames ou
   detalhes privados.
5. Coletar `systemctl --failed`, filtro critico de kernel e informacoes basicas
   de disco, RAM e temperatura.

## App e runtime

Aplicacao:

| Item | Valor |
| --- | --- |
| Repositorio | `kiosky-player` |
| Branch | `appliance-v0.1` |
| Commit da RC1 | `c71318a Add configurable MPV output flags` |
| Modo de execucao | manual como usuario `totem` |
| Config privada | `/data/config/config.json`, fora do Git |

Runtime minimo:

- `mpv`;
- `ffmpeg`;
- `python3-requests`;
- sem `python3-pip`;
- sem `python3-venv`.

Componentes fora desta fase:

- Xorg;
- Wayland;
- compositor;
- Chromium.

## Config candidata sanitizada

Campos obrigatorios da RC1:

| Campo | Valor |
| --- | --- |
| `mpv_query_uses_fresh_ipc` | `true` |
| `mpv_vo` | `gpu` |
| `mpv_gpu_context` | `drm` |
| `mpv_ao` | `null` |
| `low_resource_mode` | `false` |
| `watchdog_interval_sec` | `10` |
| `mpv_watchdog_ping_failures_before_restart` | `2` |
| `mpv_watchdog_grace_after_load_sec` | `0` |
| `mpv_watchdog_grace_after_restart_sec` | `0` |
| `mpv_ipc_timeout_sec` | `2.0` |
| `mpv_startup_timeout_sec` | `10.0` |
| `hwdec` | `auto-safe` |
| `mpv_log_file` | `/tmp/kiosky/mpv.log` |
| `mpv_msg_level` | `all=v` |
| `mpv_debug_events` | `true` |

Template publico: `docs/app-integration/config.homologation-v0.1.example.json`.

O arquivo real em `/data/config/config.json` deve conter os valores privados de
`api_url`, `api_key`, `environment_id` e `station_id` somente na placa.

## Evidencias que justificam a RC1

| Rodada | Resultado |
| --- | --- |
| [Fresh IPC query](../../evidence/candidate-a/runs/20260430-104949-kiosky-manual-probe-fresh-ipc-query/README.md) | `mpv_query_uses_fresh_ipc=true` zerou timeout de comando, ping failed, restart e falha de `loadfile`. |
| [Playback observer](../../evidence/candidate-a/runs/20260430-113008-kiosky-playback-observer/README.md) | IPC ficou estavel, mas 4 aliases nao avancaram `time-pos`/frame. |
| [MPV flags progress probe](../../evidence/candidate-a/runs/20260430-115507-mpv-flags-progress-probe/README.md) | Perfil simples fez as midias problematicas avancarem fora do app. |
| [Low resource off](../../evidence/candidate-a/runs/20260430-122532-kiosky-playback-observer-low-resource-off/README.md) | `low_resource_mode=false` sozinho nao resolveu o app real. |
| [Remaining flags matrix](../../evidence/candidate-a/runs/20260430-125237-mpv-remaining-flags-matrix/README.md) | V5, com `--vo=gpu --gpu-context=drm --ao=null`, fez aliases problematicos avancarem no MPV isolado. |
| [Explicit MPV output observer](../../evidence/candidate-a/runs/20260430-133130-kiosky-playback-observer-explicit-mpv-output/README.md) | Config candidata passou por 300s no app real, com todos os 5 aliases avancando tempo e frame. |

Resultado da rodada aprovada `20260430-133130`:

- `MPV IPC command timeout=0`;
- `MPV IPC ping failed=0`;
- `Restarting MPV=0`;
- `MPV process started=1`;
- `Failed to load media=0`;
- todos os 5 aliases avancaram `time-pos` e `estimated-frame-number`;
- `systemctl --failed=0`;
- sem `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`;
- sem escrita em `/opt`;
- sem processo remanescente real de `kiosk.py` ou `mpv`.

## Fora do escopo

Esta RC1 nao libera:

- unit `systemd` da aplicacao;
- root read-only;
- corte seco;
- producao.

Tambem continuam proibidos no fluxo de homologacao:

- `apt upgrade`;
- `apt full-upgrade`;
- `apt dist-upgrade`;
- `armbian-upgrade`;
- publicacao de secrets, URLs privadas, nomes privados, payloads privados ou
  artefatos brutos.

## Criterios de aprovacao

A homologacao da segunda placa/cartao passa se todos os itens abaixo forem
verdadeiros:

- H2testw do cartao passou sem erros.
- Imagem base gravada e primeiro boot concluido.
- Rede e SSH de bancada funcionam.
- `systemctl --failed` fica em `0 loaded units listed`.
- Filtro critico de kernel sem `Oops`, `panic`, erro EXT4, remount read-only,
  `mmc timeout` ou `mmc reset`.
- Layout `/data`, usuario `totem` e diretorios do app existem com permissoes
  esperadas.
- Runtime minimo presente: `mpv`, `ffmpeg`, `python3-requests`.
- `check_app_prereqs` aprovado.
- `kiosky-player` deployado no commit `c71318a`.
- Config privada criada fora do Git com os campos candidatos da RC1.
- Observer de 300s aprovado com metricas iguais ou melhores que a rodada
  `20260430-133130`.
- Observacao humana de 30 a 60 minutos sem regressao visual evidente.
- Sem processo remanescente real apos timeout/encerramento controlado.
- Sem escrita em `/opt/totem/kiosky-player` durante o app.

## Criterios de bloqueio

Bloquear a RC1 nessa placa/cartao se aparecer qualquer item abaixo:

- `Internal error: Oops`;
- `Kernel panic`;
- `EXT4-fs error`;
- `Aborting journal`;
- `Remounting filesystem read-only`;
- `mmc timeout` ou `mmc reset` recorrente;
- servico falhado relevante em `systemctl --failed`;
- MPV IPC command timeout maior que zero no observer;
- MPV IPC ping failed maior que zero no observer;
- restart recorrente do MPV;
- falha de `loadfile`;
- alias esperado sem avancar `time-pos` e frame;
- processo remanescente real de `kiosk.py` ou `mpv`;
- escrita em `/opt/totem/kiosky-player`;
- necessidade de `apt upgrade` ou mudanca de kernel/DTB/U-Boot/BSP para passar.

## Proximos passos

1. Provisionar a segunda placa/cartao seguindo
   [PROVISIONAMENTO_SEGUNDA_PLACA.md](PROVISIONAMENTO_SEGUNDA_PLACA.md).
2. Executar o [CHECKLIST_HOMOLOGACAO.md](CHECKLIST_HOMOLOGACAO.md).
3. Rodar observer de homologacao por 300s.
4. Fazer teste manual observado de 30 a 60 minutos com a mesma config.
5. Se passar, preparar validacao controlada da unit `systemd` da aplicacao.
6. Manter root read-only, corte seco e producao bloqueados ate novas rodadas
   especificas.
