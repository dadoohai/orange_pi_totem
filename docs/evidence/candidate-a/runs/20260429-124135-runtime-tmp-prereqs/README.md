# Rodada 20260429-124135 - Runtime tmp prereqs

Status: `/tmp/kiosky` garantido e `check_app_prereqs.sh` aprovado; MPV/app/systemd nao foram iniciados.

## Objetivo

Garantir o diretorio temporario `/tmp/kiosky` de forma idempotente e repetir o `check_app_prereqs.sh` apos a instalacao do runtime minimo.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/check_app_prereqs.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefato bruto novo da rodada:

- `totem-diag-20260429-124130-0300.tar.gz`

O pull com padrao `totem-diag-*.tar.gz` tambem copiou diagnosticos antigos ainda presentes em `/root/totem-diag`. A analise desta rodada usa o `totem-diag-20260429-124130-0300`.

Os arquivos `.tar.gz` sao evidencia bruta e nao devem ser commitados no repositorio publico. Eles podem conter IPs locais, IPv6, hostname, UUIDs do NetworkManager e logs detalhados.

## Runtime Temporario

Estado antes:

```text
/tmp/kiosky does not exist
```

Estado depois:

```text
drwxr-x--- totem totem /tmp/kiosky
```

O script criou somente `/tmp/kiosky`, com owner `totem:totem` e modo `0750`.

## Check App Prereqs

Resultado de `check_app_prereqs.sh`: aprovado.

Itens confirmados:

- `python3` encontrado em `/usr/bin/python3`.
- `python3-requests` disponivel, versao `2.28.1`.
- Modulo `venv` responde.
- `mpv` encontrado em `/usr/bin/mpv`.
- Usuario `totem` existe.
- Grupo `totem` existe.
- Diretorios persistentes em `/data` existem com ownership esperado.
- `/tmp/kiosky` existe com owner `totem:totem`.
- `/data/media/kiosky-player` e gravavel pelo usuario `totem`.

Pendencias/avisos esperados:

- `pip` nao encontrado.
- `/opt/totem/venv` existe, mas ainda nao tem `bin/python`.
- `/opt/totem/venv` existe, mas ainda nao tem `bin/pip`.

Esses avisos permanecem esperados porque `python3-pip` e `python3-venv` nao foram instalados nesta fase e o venv ainda nao foi inicializado.

## Diagnostico Pos-Check

- `systemctl --failed`: `0 loaded units listed`.
- Kernel tainted: `1024`, ja observado em rodadas anteriores.
- Filtro critico do kernel sem `oops`.
- Filtro critico do kernel sem `panic`.
- Filtro critico do kernel sem `EXT4-fs error`.
- Filtro critico do kernel sem `Aborting journal`.
- Filtro critico do kernel sem `Remounting filesystem read-only`.
- Filtro critico do kernel sem `mmc.*timeout`.
- Filtro critico do kernel sem `mmc.*reset`.
- Filtro critico do kernel sem `voltage`.

O filtro ainda mostra mensagens conhecidas de boot como `thermal_sys` e `Error applying setting, reverse things back` para UART/SPI/MMC, sem regressao critica observada nesta rodada.

## Escopo Negativo Confirmado

- Nenhum comando `apt` foi executado.
- MPV nao foi iniciado.
- `kiosk.py` nao foi iniciado.
- Nenhum servico systemd da aplicacao foi ativado.
- `deploy_kiosky_player.sh` nao foi executado.
- Nenhum servico foi alterado.
- Nenhum commit foi feito.

## Proximos Passos

- Fazer teste manual de MPV, ainda sem iniciar `kiosk.py`.
- Depois fazer deploy controlado do app e teste manual supervisionado.
- Transformar a garantia de `/tmp/kiosky` em mecanismo definitivo da aplicacao, preferencialmente `RuntimeDirectory` na unit systemd futura.
- So depois avaliar systemd, root read-only e corte seco.
