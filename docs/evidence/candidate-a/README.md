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
| Analise de midias problematicas | 2026-04-29 | Consolidou a suspeita inicial de midia/transicao antes dos probes isolados posteriores | [04_ANALISE_MIDIAS_PROBLEMATICAS.md](../../app-integration/04_ANALISE_MIDIAS_PROBLEMATICAS.md) |
| Midia isolada suspeita | 2026-04-29 | Alias suspeito tocou com `vo=null` e via DRM/KMS como `totem`, encerrando por EOF; arquivo corrompido ficou improvavel | [Rodada 20260429-235338-media-isolated-suspect](runs/20260429-235338-media-isolated-suspect/README.md) |
| Transicao de midia controlada | 2026-04-30 | `loadfile` controle -> suspeita -> controle retornou `success` e nao reproduziu a falha anterior | [Rodada 20260430-002436-media-transition-suspect](runs/20260430-002436-media-transition-suspect/README.md) |
| Playlist watchdog probe | 2026-04-30 | Playlist completa com duracoes configuradas e pings concorrentes passou sem timeout de `loadfile` ou ping | [Rodada 20260430-004100-media-playlist-watchdog-probe](runs/20260430-004100-media-playlist-watchdog-probe/README.md) |
| MPVController playlist probe | 2026-04-30 | `load_file` passou 5/5, mas `ping()` e `get_property()` pelo controller persistente deram timeout; foco mudou para IPC persistente | [Rodada 20260430-011115-mpv-controller-playlist-probe](runs/20260430-011115-mpv-controller-playlist-probe/README.md) |
| Fresh IPC query | 2026-04-30 | `mpv_query_uses_fresh_ipc=true` estabilizou IPC/watchdog/loadfile: timeouts, ping failed, restarts e falhas de load ficaram em 0 | [Rodada 20260430-104949-kiosky-manual-probe-fresh-ipc-query](runs/20260430-104949-kiosky-manual-probe-fresh-ipc-query/README.md) |
| Playback observer do app | 2026-04-30 | IPC estavel; observador externo mostrou 4 aliases sem avancar `time-pos`/frame e 1 alias avancando normalmente | [Rodada 20260430-113008-kiosky-playback-observer](runs/20260430-113008-kiosky-playback-observer/README.md) |
| MPV flags progress probe | 2026-04-30 | Fora do app, flags app/low-resource pararam 4 aliases; perfil simples fez todos avancarem | [Rodada 20260430-115507-mpv-flags-progress-probe](runs/20260430-115507-mpv-flags-progress-probe/README.md) |
| App com `low_resource_mode=false` | 2026-04-30 | IPC continuou estavel, mas 4 aliases seguiram sem avancar; remover low-resource isoladamente nao resolveu | [Rodada 20260430-122532-kiosky-playback-observer-low-resource-off](runs/20260430-122532-kiosky-playback-observer-low-resource-off/README.md) |
| Remaining flags matrix | 2026-04-30 | V5, com `--vo=gpu --gpu-context=drm --ao=null`, fez aliases problematicos avancarem e preservou o alias bom | [Rodada 20260430-125237-mpv-remaining-flags-matrix](runs/20260430-125237-mpv-remaining-flags-matrix/README.md) |
| Observer com saida MPV explicita | 2026-04-30 | Config candidata aprovada no app real por 300s: IPC/loadfile estaveis, 0 restarts e todos os 5 aliases avancando `time-pos`/frame | [Rodada 20260430-133130-kiosky-playback-observer-explicit-mpv-output](runs/20260430-133130-kiosky-playback-observer-explicit-mpv-output/README.md) |
| Systemd dev smoke | 2026-04-30 | Aprovado em desenvolvimento; `systemctl start/stop` com HDMI conectado, sem escrita em `/opt` e sem processo remanescente apos stop | [Rodada 20260430-174718-systemd-dev-smoke](runs/20260430-174718-systemd-dev-smoke/README.md) |
| Systemd dev autoboot | 2026-04-30 | Aprovado em desenvolvimento; servico habilitado e validado em dois reboots controlados com HDMI conectado | [Rodada 20260430-185824-systemd-dev-autoboot](runs/20260430-185824-systemd-dev-autoboot/README.md) |
| Systemd dev HDMI missing | 2026-04-30 | Aprovado em desenvolvimento; boot sem HDMI publicou `display_missing`, nao iniciou app/MPV e recuperou apos reconexao | [Rodada 20260430-194110-systemd-dev-hdmi-missing](runs/20260430-194110-systemd-dev-hdmi-missing/README.md) |
| Status aggregator dev service | 2026-05-01 | Aprovado em desenvolvimento; gerou `status.json` e `status.svg` publicos, sanitizados, sem renderer visual | [Rodada 20260501-121221-status-aggregator-dev-service](runs/20260501-121221-status-aggregator-dev-service/README.md) |
| Status aggregator HDMI missing/reconnection | 2026-05-01 | HDMI ausente/reconexao funcionou, mas revelou falta de convergencia do status para `player_running` apos reconexao | [Rodada 20260501-123806-status-aggregator-hdmi-missing](runs/20260501-123806-status-aggregator-hdmi-missing/README.md) |
| Status aggregator refresh HDMI | 2026-05-01 | Aprovado em desenvolvimento; refresh periodico convergiu o status agregado para `player_running` apos reconexao | [Rodada 20260501-132142-status-aggregator-refresh-hdmi](runs/20260501-132142-status-aggregator-refresh-hdmi/README.md) |
| Status aggregator config_missing | 2026-05-01 | Aprovado em desenvolvimento; config ausente/invalida gerou `config_missing`, manteve servico ativo e nao iniciou app/MPV | [Rodada 20260501-141332-status-aggregator-config-missing](runs/20260501-141332-status-aggregator-config-missing/README.md) |
| Status renderer config_missing | 2026-05-01 | Aprovado em desenvolvimento; renderer Dadooh exibiu `config_missing`, sem rodar junto com o MPV principal | [Rodada 20260501-145916-status-renderer-config-missing](runs/20260501-145916-status-renderer-config-missing/README.md) |
| Status renderer visual B1 | 2026-05-01 | Aprovado em desenvolvimento; tela "Configuracao pendente" observada por humano e restauracao para `player_running` validada | [Rodada 20260501-190932-status-renderer-visual-b1](runs/20260501-190932-status-renderer-visual-b1/README.md) |

Resumo: o Wi-Fi cliente 5 GHz foi aprovado e permaneceu funcional nas validacoes posteriores a desativacao de `bluetooth.service` e `aw859a-bluetooth.service`.
O MPV manual tambem foi aprovado via DRM/KMS direto, inclusive como usuario `totem`, sem indicacao atual para instalar Xorg, Wayland ou compositor. O app ja foi deployado e rodou manualmente; a camada OS permanece saudavel, mas o Candidato A ainda nao esta homologado para producao. O bloqueio app-MPV curto foi resolvido para a candidata atual: IPC/watchdog/loadfile foi estabilizado por `mpv_query_uses_fresh_ipc=true`, a saida MPV explicita foi aprovada, e todos os 5 aliases avancaram no app real. O proximo passo e homologacao `v0.1-rc1` em segunda placa/cartao e teste manual mais longo.

Evolucao sanitizada das metricas do MPV:

- Logs por geracao: `Restarting MPV=31`, `MPV process started=32`, `Failed to load media=10`.
- Timeout IPC 5s: manteve `Restarting MPV=31` e `MPV process started=32`, piorando `Failed to load media=13`.
- Watchdog threshold 2: reduziu `Restarting MPV=18`, `MPV process started=19`, `Failed to load media=7`.
- Threshold 2 com reset por geracao: reduziu pouco mais para `Restarting MPV=17`, `MPV process started=18`, mas deixou 3 `Bad file descriptor`.
- Coordenacao IPC/restart: zerou `Bad file descriptor`/command send failed, reduziu `Restarting MPV=13`, `MPV process started=14`, `Failed to load media=2`, mas manteve `MPV IPC ping failed=23` e `MPV IPC unresponsive=11`.
- Fresh IPC query: `MPV IPC command timeout=0`, `MPV IPC ping failed=0`, `Restarting MPV=0`, `MPV process started=1` e `Failed to load media=0`.
- Playback observer: com IPC estavel, 4 aliases ficaram sem progressao real de `time-pos`/frame, apesar de `pause=false`, `idle-active=false` e `eof-reached=false`.
- Remaining flags matrix: adicionar `--vo=gpu --gpu-context=drm --ao=null` ao perfil do app fez os aliases problematicos avancarem no MPV isolado.
- Observer com saida MPV explicita: `MPV IPC command timeout=0`, `MPV IPC ping failed=0`, `Restarting MPV=0`, `MPV process started=1`, `Failed to load media=0` e todos os 5 aliases avancando `time-pos`/frame no app real.

## Resumo atual pos-RC1

A homologacao `v0.1-rc1` continua separada e usa a configuracao candidata
validada em `20260430-133130`: `mpv_query_uses_fresh_ipc=true`, `mpv_vo=gpu`,
`mpv_gpu_context=drm`, `mpv_ao=null` e `low_resource_mode=false`, ainda como
frente de homologacao, nao producao.

Depois da RC1, na placa de desenvolvimento, foram aprovados `systemd`
start/stop, autoboot, HDMI ausente/reconexao, status aggregator com refresh,
`config_missing`, renderer visual Dadooh e B1 "Configuracao pendente". Esses
resultados sao desenvolvimento pos-RC1; nao reclassificam retroativamente a
homologacao.

Pendencias antes de qualquer decisao de producao: revisar o ruido amplo de
kernel da rodada B1, executar teste longo em homologacao 2, validar
`player_error` visual, planejar e implementar onboarding Wi-Fi/configuracao,
validar root read-only e corte seco, e definir monitoramento/update/rollback.

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
./scripts/remote/pull_artifacts.sh <usuario>@<host-de-bancada> docs/evidence/candidate-a/runs/2026-04-28/
```

O script copia apenas arquivos `.tar.gz` de `/root/totem-diag/` e nao apaga nada na placa. Por padrao ele copia todos os `.tar.gz`; para melhorar rastreabilidade, use o terceiro argumento para filtrar a rodada desejada:

```bash
./scripts/remote/pull_artifacts.sh <usuario>@<host-de-bancada> docs/evidence/candidate-a/runs/20260429-012638-data-layout/ "totem-diag-20260429-012629-0300.tar.gz"
./scripts/remote/pull_artifacts.sh <usuario>@<host-de-bancada> docs/evidence/candidate-a/runs/20260429-012638-data-layout/ "totem-diag-20260429-0126*.tar.gz"
```

Os artefatos brutos (`.tar.gz`, diretorios `raw/` e diretorios `extracted/`) devem ficar fora do Git porque podem conter IPs, hostnames, SSIDs, UUIDs e detalhes de rede. Cada rodada em `docs/evidence/candidate-a/runs/<timestamp>/` deve ter um `README.md` sanitizado com o resumo publicavel.

## Sequencia de base ja exercitada

1. `collect_diag.sh`
2. `network_snapshot.sh`
3. `pull_artifacts.sh`
4. `setup_data_layout.sh`
5. `disable_bluetooth.sh` somente apos baseline coletado

Proximo passo operacional planejado: provisionar a homologacao `v0.1-rc1` em segunda placa/cartao, manter `mpv_query_uses_fresh_ipc=true`, `mpv_vo=gpu`, `mpv_gpu_context=drm`, `mpv_ao=null` e `low_resource_mode=false`, repetir o observer do app real por 300s, preservar DRM/KMS como caminho principal e manter systemd da aplicacao bloqueado.

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
./scripts/remote/push_and_run.sh <usuario>@<host-de-bancada> scripts/board/wifi_snapshot.sh
./scripts/remote/push_and_run.sh <usuario>@<host-de-bancada> scripts/board/wifi_client_test.sh "<nome-da-conexao>"
./scripts/remote/pull_artifacts.sh <usuario>@<host-de-bancada> docs/evidence/candidate-a/runs/<timestamp>-wifi-client/ "wifi-*.tar.gz"
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
./scripts/remote/push_and_run.sh <usuario>@<host-de-bancada> scripts/board/collect_diag.sh
./scripts/remote/push_and_run.sh <usuario>@<host-de-bancada> scripts/board/network_snapshot.sh
./scripts/remote/pull_artifacts.sh <usuario>@<host-de-bancada> docs/evidence/candidate-a/runs/2026-04-28/
./scripts/remote/push_and_run.sh <usuario>@<host-de-bancada> scripts/board/stress_light_30m.sh
./scripts/remote/push_and_run.sh <usuario>@<host-de-bancada> scripts/board/setup_data_layout.sh
./scripts/remote/push_and_run.sh <usuario>@<host-de-bancada> scripts/board/disable_bluetooth.sh
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
- Homologar a configuracao `v0.1-rc1` em segunda placa/cartao.
- Repetir observer de 300s com a configuracao candidata, ainda sem systemd.
- Rodar teste manual observado de 30 a 60 minutos somente apos a segunda placa passar no observer curto.
- Liberar systemd da aplicacao somente depois de estabilidade manual comprovada.
- Validar root read-only.
- Validar comportamento com cortes de energia em bancada controlada.
