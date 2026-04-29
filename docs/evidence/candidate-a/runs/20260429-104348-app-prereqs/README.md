# Rodada 20260429-104348 - Preparacao da aplicacao

Status: preparacao de usuario e diretorios concluida; pre-requisitos da aplicacao com pendencias esperadas antes do deploy.

## Objetivo

Preparar usuario/diretorios da aplicacao e verificar pre-requisitos sem fazer deploy do app, sem iniciar `kiosk.py`, sem iniciar MPV, sem ativar systemd da aplicacao e sem executar `apt`.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/board/setup_totem_user.sh`
- `scripts/board/setup_app_dirs.sh`
- `scripts/board/check_app_prereqs.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefato bruto copiado localmente:

- `totem-diag-20260429-104338-0300.tar.gz`

O arquivo `.tar.gz` e evidencia bruta e nao deve ser commitado no repositorio publico. Ele pode conter IPs locais, IPv6, hostname, UUIDs do NetworkManager e detalhes de logs.

## Usuario

Resultado de `setup_totem_user.sh`:

- Grupo `totem` criado.
- Usuario `totem` criado.
- Usuario configurado com home `/nonexistent`.
- Usuario configurado com shell `nologin`.

## Diretorios

Resultado de `setup_app_dirs.sh`:

- `/opt/totem`: criado, `root:root`.
- `/opt/totem/kiosky-player`: criado, `root:root`.
- `/opt/totem/venv`: criado, `root:root`.
- `/data/config`: ajustado para `totem:totem`.
- `/data/media/kiosky-player`: criado, `totem:totem`.
- `/data/state/kiosky-player`: criado, `totem:totem`.
- `/data/spool/kiosky-player`: criado, `totem:totem`.
- `/data/logs/kiosky-player`: criado, `totem:totem`.
- `/tmp/kiosky`: criado, `totem:totem`.

## Pre-Requisitos

Resultado de `check_app_prereqs.sh`: `exit_code=1`.

Itens OK:

- `python3` encontrado.
- Modulo `venv` do Python disponivel.
- Usuario `totem` existe.
- Grupo `totem` existe.
- Diretorios esperados existem com ownership esperado.
- `/data/media/kiosky-player` e gravavel pelo usuario `totem`.

Pendencias antes do deploy:

- `mpv` nao encontrado. Registrado como pre-requisito pendente, nao como falha da base.
- `pip` nao encontrado.
- `/opt/totem/venv` existe, mas ainda nao tem `bin/python` executavel.
- `/opt/totem/venv` existe, mas ainda nao tem `bin/pip` executavel.

Nenhum pacote foi instalado nesta rodada.

## Diagnostico Do Sistema

- `systemctl --failed`: 1 unidade falhada, `aw859a-bluetooth.service`.
- `kernel tainted`: `1024`, observado e aceito nesta fase.
- Filtro critico do kernel sem `Internal error: Oops`.
- Filtro critico do kernel sem `kernel panic`.
- Filtro critico do kernel sem `EXT4-fs error`.
- Filtro critico do kernel sem `Aborting journal`.
- Filtro critico do kernel sem `Remounting filesystem read-only`.
- Filtro critico do kernel sem `mmc timeout/reset`.

O filtro amplo do kernel ainda mostra mensagens conhecidas de boot como `thermal_sys` e `Error applying setting, reverse things back` para UART/SPI/MMC, sem impacto critico observado nesta rodada.

## Escopo Negativo Confirmado

- Nenhum deploy do app foi executado.
- `kiosk.py` nao foi iniciado.
- MPV nao foi iniciado.
- Nenhum servico systemd da aplicacao foi ativado.
- Nenhum comando `apt` foi executado.

## Conclusao

A preparacao basica de usuario e diretorios foi concluida. O deploy ainda depende de resolver os pre-requisitos da aplicacao, especialmente `mpv`, `pip` e inicializacao do venv. Tambem fica registrado o ponto de atencao em `aw859a-bluetooth.service` falhado para decisao posterior.
