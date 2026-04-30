# Evidencias - Candidato A

Status: em validacao. O Candidato A ainda nao esta homologado para producao.

## Composicao da imagem

| Item | Valor |
| --- | --- |
| Build | Armbian Build v25.11 |
| Release | Debian Bookworm Minimal |
| Board | Orange Pi Zero 3 |
| Kernel | `6.12.58-current-sunxi64` |
| U-Boot | `2025.04` |
| BSP freeze | `BSPFREEZE=yes` |
| Rede | NetworkManager |
| Desktop | ausente |

## Regra operacional

Nao executar atualizacao ampla em campo. Kernel, DTB, U-Boot e BSP permanecem congelados; qualquer mudanca de sistema operacional deve gerar nova imagem e nova homologacao.

## Evidencias ja registradas

| Teste | Data | Resultado | Evidencia |
| --- | --- | --- | --- |
| Boot inicial | 2026-04-28 | Aprovado | [Testes iniciais](../../03_TESTES_INICIAIS_E_EVIDENCIAS.md) |
| Reboots curtos | 2026-04-28 | Aprovado | [Testes iniciais](../../03_TESTES_INICIAIS_E_EVIDENCIAS.md) |
| Baseline de rede cabeada/NetworkManager | 2026-04-28 | Aprovado | [network-before-stress.txt](../../EVIDENCIAS/2026-04-28/network-before-stress.txt) |
| Stress leve CPU/RAM 30 min | 2026-04-28 | Aprovado | [stress-30m.txt](../../EVIDENCIAS/2026-04-28/stress-30m.txt) |
| Layout `/data` | 2026-04-29 | Aprovado | [Rodada 20260429-012638-data-layout](runs/20260429-012638-data-layout/README.md) |
| Wi-Fi cliente 5 GHz | 2026-04-29 | Aprovado | [Rodada 20260429-020919-wifi-test-ap304-5g](runs/20260429-020919-wifi-test-ap304-5g/README.md) |
| Desabilitar `bluetooth.service` | 2026-04-29 | Aprovado | [Rodada 20260429-022612-disable-bluetooth](runs/20260429-022612-disable-bluetooth/README.md) |
| Usuario/diretorios e pre-requisitos iniciais do app | 2026-04-29 | Preparacao aprovada; runtime ainda pendente naquela rodada | [Rodada 20260429-104348-app-prereqs](runs/20260429-104348-app-prereqs/README.md) |
| Desabilitar `aw859a-bluetooth.service` | 2026-04-29 | Aprovado | [Rodada 20260429-110054-disable-aw859a-bluetooth](runs/20260429-110054-disable-aw859a-bluetooth/README.md) |
| Instalacao de runtime minimo | 2026-04-29 | Aprovado; `mpv`, `ffmpeg` e `python3-requests` instalados | [Rodada 20260429-123146-runtime-packages-install](runs/20260429-123146-runtime-packages-install/README.md) |
| Runtime tmp e pre-requisitos | 2026-04-29 | Aprovado; `/tmp/kiosky` garantido e `check_app_prereqs.sh` passou | [Rodada 20260429-124135-runtime-tmp-prereqs](runs/20260429-124135-runtime-tmp-prereqs/README.md) |
| MPV manual DRM/KMS | 2026-04-29 | Aprovado; `vo=drm` e `vo=gpu --gpu-context=drm` funcionaram como root e como usuario `totem`, com confirmacao visual HDMI | [Rodada 20260429-131803-mpv-manual-probe](runs/20260429-131803-mpv-manual-probe/README.md) |
| Primeiro run manual `kiosky-player` | 2026-04-29 | Aprovado com ressalvas; app rodou como `totem`, baixou midias, criou estado/status, nao escreveu em `/opt`, mas teve 21 `MPV IPC unresponsive` e 5 `Failed to load media` | [Rodada 20260429-144234-kiosky-manual-probe](runs/20260429-144234-kiosky-manual-probe/README.md) |
| Analise do primeiro run | 2026-04-29 | Confirmou base OS saudavel e concentrou a investigacao em MPV IPC/watchdog/restart | [Analise primeiro run](../../app-integration/02_ANALISE_PRIMEIRO_RUN_KIOSKY.md) |
| Run instrumentado MPV/IPC | 2026-04-29 | Diagnostico ampliado; 31 restarts, 32 processos MPV, 21 IPC unresponsive e 10 falhas de load | [Rodada 20260429-164413-kiosky-manual-probe-instrumented](runs/20260429-164413-kiosky-manual-probe-instrumented/README.md) |
| Logs MPV por geracao | 2026-04-29 | 32 logs `mpv-g*.log`; IPC startup completo em 32/32 geracoes; problema deslocado para responsividade posterior | [Rodada 20260429-172733-kiosky-manual-probe-generation-logs](runs/20260429-172733-kiosky-manual-probe-generation-logs/README.md) |
| A/B timeout IPC 5s | 2026-04-29 | Timeout maior reduziu levemente timeouts, mas manteve 31 restarts/32 processos e piorou falhas de load para 13 | [Rodada 20260429-174349-kiosky-manual-probe-ipc-timeout-5s](runs/20260429-174349-kiosky-manual-probe-ipc-timeout-5s/README.md) |
| Hipoteses MPV IPC/watchdog | 2026-04-29 | Hipoteses mais fortes: watchdog agressivo, corrida IPC/restart e ping IPC pouco responsivo; systemd/kernel/SD ficaram baixa prioridade | [Hipoteses MPV IPC e watchdog](../../app-integration/03_HIPOTESES_MPV_IPC_WATCHDOG.md) |
| Watchdog threshold 2 | 2026-04-29 | Reduziu `Restarting MPV` 31->18, `MPV process started` 32->19 e `Failed to load media` 10->7 | [Rodada 20260429-194954-kiosky-manual-probe-watchdog-threshold-2](runs/20260429-194954-kiosky-manual-probe-watchdog-threshold-2/README.md) |
| Watchdog threshold 2 com reset por geracao | 2026-04-29 | Corrigiu semantica do contador; ganho pequeno sobre threshold 2 e ainda restaram timeouts/`Bad file descriptor` | [Rodada 20260429-202035-kiosky-manual-probe-watchdog-threshold-2-generation-reset](runs/20260429-202035-kiosky-manual-probe-watchdog-threshold-2-generation-reset/README.md) |
| Coordenacao IPC/restart | 2026-04-29 | Commit `9bdb38c` zerou `Bad file descriptor` e command send failed; reduziu restarts para 13, processos MPV para 14 e falhas de load para 2 | [Rodada 20260429-210204-kiosky-manual-probe-ipc-restart-coordination](runs/20260429-210204-kiosky-manual-probe-ipc-restart-coordination/README.md) |
| Evolucao MPV IPC/watchdog | 2026-04-29 | Consolidacao comparativa das metricas e dos criterios para proximo A/B, teste longo e systemd futuro | [04_EVOLUCAO_MPV_IPC_WATCHDOG.md](../../app-integration/04_EVOLUCAO_MPV_IPC_WATCHDOG.md) |

Resumo: o Wi-Fi cliente 5 GHz foi aprovado e permaneceu funcional nas validacoes posteriores a desativacao de `bluetooth.service` e `aw859a-bluetooth.service`.
O MPV manual tambem foi aprovado via DRM/KMS direto, inclusive como usuario `totem`, sem indicacao atual para instalar Xorg, Wayland ou compositor. O app ja foi deployado e rodou manualmente; a camada OS permanece saudavel, mas o Candidato A ainda nao esta homologado para producao porque o bloqueio atual e app-MPV: IPC ping, watchdog e restart.

Evolucao sanitizada das metricas do MPV:

- Logs por geracao: `Restarting MPV=31`, `MPV process started=32`, `Failed to load media=10`.
- Timeout IPC 5s: manteve `Restarting MPV=31` e `MPV process started=32`, piorando `Failed to load media=13`.
- Watchdog threshold 2: reduziu `Restarting MPV=18`, `MPV process started=19`, `Failed to load media=7`.
- Threshold 2 com reset por geracao: reduziu pouco mais para `Restarting MPV=17`, `MPV process started=18`, mas deixou 3 `Bad file descriptor`.
- Coordenacao IPC/restart: zerou `Bad file descriptor`/command send failed, reduziu `Restarting MPV=13`, `MPV process started=14`, `Failed to load media=2`, mas manteve `MPV IPC ping failed=23` e `MPV IPC unresponsive=11`.

## Coletas padronizadas

Os scripts de bancada ficam em `scripts/board/` e gravam artefatos em `/root/totem-diag/` na placa.

| Script | Saida esperada |
| --- | --- |
| `collect_diag.sh` | diretorio `/root/totem-diag/<timestamp>/` e arquivo `/root/totem-diag/totem-diag-<timestamp>.tar.gz` |
| `network_snapshot.sh` | diretorio `/root/totem-diag/network-<timestamp>/` e arquivo `/root/totem-diag/network-snapshot-<timestamp>.tar.gz` |
| `wifi_snapshot.sh` | diretorio `/root/totem-diag/wifi-snapshot-<timestamp>/` e arquivo `/root/totem-diag/wifi-snapshot-<timestamp>.tar.gz` |
| `wifi_client_test.sh` | diretorio `/root/totem-diag/wifi-client-<timestamp>/` e arquivo `/root/totem-diag/wifi-client-<timestamp>.tar.gz` |
| `stress_light_30m.sh` | diretorio `/root/totem-diag/stress-light-30m-<timestamp>/` e arquivo `/root/totem-diag/stress-light-30m-<timestamp>.tar.gz` |
| `disable_bluetooth.sh` | diretorio `/root/totem-diag/bluetooth-disable-<timestamp>/` e arquivo `/root/totem-diag/bluetooth-disable-<timestamp>.tar.gz` |

Para copiar os artefatos da placa para o repositorio local, depois que SSH estiver liberado:

```bash
./scripts/remote/pull_artifacts.sh root@orangepizero3 docs/evidence/candidate-a/runs/2026-04-28/
```

O script copia apenas arquivos `.tar.gz` de `/root/totem-diag/` e nao apaga nada na placa. Por padrao ele copia todos os `.tar.gz`; para melhorar rastreabilidade, use o terceiro argumento para filtrar a rodada desejada:

```bash
./scripts/remote/pull_artifacts.sh root@orangepizero3 docs/evidence/candidate-a/runs/20260429-012638-data-layout/ "totem-diag-20260429-012629-0300.tar.gz"
./scripts/remote/pull_artifacts.sh root@orangepizero3 docs/evidence/candidate-a/runs/20260429-012638-data-layout/ "totem-diag-20260429-0126*.tar.gz"
```

Os artefatos brutos (`.tar.gz`, diretorios `raw/` e diretorios `extracted/`) devem ficar fora do Git porque podem conter IPs, hostnames, SSIDs, UUIDs e detalhes de rede. Cada rodada em `docs/evidence/candidate-a/runs/<timestamp>/` deve ter um `README.md` sanitizado com o resumo publicavel.

## Sequencia de base ja exercitada

1. `collect_diag.sh`
2. `network_snapshot.sh`
3. `pull_artifacts.sh`
4. `setup_data_layout.sh`
5. `disable_bluetooth.sh` somente apos baseline coletado

Proximo passo operacional planejado: fazer A/B curto com `mpv_watchdog_ping_failures_before_restart=999`, preservando DRM/KMS como caminho principal e mantendo systemd da aplicacao bloqueado.

Estado corrente dos pre-requisitos: `check_app_prereqs.sh` passou apos a instalacao de `mpv`, `ffmpeg`, `python3-requests` e a criacao de `/tmp/kiosky`. O MPV manual via DRM/KMS passou como root e como `totem`, com confirmacao visual HDMI. O app foi deployado em `/opt/totem/kiosky-player`, a config privada existe em `/data/config/config.json`, e os runs manuais criaram dados em `/data` e `/tmp` sem escrita em `/opt`. `pip`, `/opt/totem/venv`, Xorg, Wayland, compositor e Chromium continuam fora desta fase por decisao de escopo.

Observacao: `disable_bluetooth.sh` desabilita o servico userland quando ele existe. Ele pode nao remover logs de Bluetooth caso a mensagem venha do driver/kernel antes do servico `bluetooth.service`.

## Validacao Wi-Fi cliente

A validacao de Wi-Fi cliente deve usar apenas conexoes ja existentes no NetworkManager. Os scripts nao pedem senha, nao registram senha, nao criam conexoes novas, nao apagam conexoes salvas e nao devem desconectar Ethernet nesta fase.

Sequencia recomendada:

1. Rodar `wifi_snapshot.sh` para capturar o estado Wi-Fi sem alterar nada.
2. Escolher uma conexao Wi-Fi ja existente em `nmcli connection show`.
3. Rodar `wifi_client_test.sh "<nome-da-conexao>"`.
4. Copiar os artefatos com `pull_artifacts.sh`, preferencialmente filtrando pelo timestamp da rodada.

Exemplo:

```bash
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/wifi_snapshot.sh
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/wifi_client_test.sh "<nome-da-conexao>"
./scripts/remote/pull_artifacts.sh root@orangepizero3 docs/evidence/candidate-a/runs/<timestamp>-wifi-client/ "wifi-*.tar.gz"
```

Ethernet deve permanecer conectada durante esta validacao para manter caminho de acesso e recuperacao. Hotspot/configurador e modo manutencao sao etapa posterior; nao fazem parte deste teste.

Artefatos brutos de Wi-Fi podem conter SSID, IPs, nomes de conexao, rotas e logs do NetworkManager. Nao commitar `.tar.gz` brutos no repositorio publico; registrar apenas README sanitizado por rodada.

### Resultado registrado - 20260429-020919-wifi-test-ap304-5g

A rodada [20260429-020919-wifi-test-ap304-5g](runs/20260429-020919-wifi-test-ap304-5g/README.md) aprovou a validacao de Wi-Fi cliente em 5 GHz com dados sensiveis redigidos:

- `wlan0` conectou usando conexao NetworkManager existente.
- `wlan0` recebeu IP.
- `ping -I wlan0 -c 4 1.1.1.1` funcionou com 0% de perda.
- Ethernet permaneceu conectada.
- `systemctl --failed`: `0 loaded units listed`.
- `kernel tainted`: `1024`, observado e aceito nesta fase.
- Sem `Internal error: Oops`, `kernel panic`, `EXT4-fs error`, `Remounting filesystem read-only` ou `mmc timeout/reset`.
- Artefatos brutos da rodada permanecem fora do Git.

## Template de registro

### Identificacao

- Data:
- Operador:
- Placa:
- Fonte:
- Cartao microSD:
- Imagem:
- Hash da imagem:
- Observacoes de bancada:

### Comandos executados

```bash
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/collect_diag.sh
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/network_snapshot.sh
./scripts/remote/pull_artifacts.sh root@orangepizero3 docs/evidence/candidate-a/runs/2026-04-28/
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/stress_light_30m.sh
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/setup_data_layout.sh
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/disable_bluetooth.sh
```

### Artefatos coletados

| Artefato | Origem na placa | Destino no repositorio | Observacoes |
| --- | --- | --- | --- |
|  | `/root/totem-diag/` | `docs/evidence/candidate-a/` |  |

### Resultado

- Resultado geral:
- Falhas observadas:
- Reboots realizados:
- Temperatura observada:
- Rede cabeada:
- Wi-Fi:
- Bluetooth:
- Kernel tainted:
- Servicos falhados:

### Criterios para prosseguir

- Sem `kernel panic`.
- Sem `Internal error: Oops`.
- Sem erro EXT4.
- Sem reset ou timeout recorrente de MMC.
- Sem servico falhado relevante em `systemctl --failed`.
- Pacotes criticos Armbian permanecem em hold.
- NetworkManager mantem conectividade esperada.

### Pendencias

- Validar Wi-Fi de campo.
- Validar hotspot, se entrar no escopo.
- Validar aplicacao do totem depois do teste manual de MPV aprovado.
- Validar politica de logs.
- Decidir estrategia futura de `pip`/venv somente se a estabilizacao do app exigir.
- Resolver MPV IPC/watchdog/restart antes de teste longo.
- Fazer A/B curto com `mpv_watchdog_ping_failures_before_restart=999`, ainda sem systemd.
- Liberar teste manual mais longo somente apos rodada curta estavel.
- Liberar systemd da aplicacao somente depois de estabilidade manual comprovada.
- Validar root read-only.
- Validar comportamento com cortes de energia em bancada controlada.
