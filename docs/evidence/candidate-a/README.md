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

Resumo: o Wi-Fi cliente 5 GHz foi aprovado e permaneceu funcional nas validacoes posteriores a desativacao de `bluetooth.service` e `aw859a-bluetooth.service`.
O MPV manual tambem foi aprovado via DRM/KMS direto, inclusive como usuario `totem`, sem indicacao atual para instalar Xorg, Wayland ou compositor.

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

Proximo passo operacional planejado: fazer teste manual controlado do player/app, preservando DRM/KMS como caminho principal, ainda sem habilitar systemd da aplicacao.

Estado corrente dos pre-requisitos: `check_app_prereqs.sh` passou apos a instalacao de `mpv`, `ffmpeg`, `python3-requests` e a criacao de `/tmp/kiosky`. O MPV manual via DRM/KMS passou como root e como `totem`, com confirmacao visual HDMI. `pip`, `/opt/totem/venv`, Xorg, Wayland, compositor e Chromium continuam fora desta fase por decisao de escopo.

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
- Decidir estrategia futura de `pip`/venv somente se o deploy do app exigir.
- Fazer deploy controlado do app.
- Validar root read-only.
- Validar comportamento com cortes de energia em bancada controlada.
