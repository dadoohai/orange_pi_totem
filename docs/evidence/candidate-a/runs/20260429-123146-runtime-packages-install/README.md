# Rodada 20260429-123146 - Runtime packages install

Status: runtime minimo instalado; MPV/app/systemd nao foram iniciados.

## Objetivo

Instalar de forma controlada o runtime minimo para o primeiro teste futuro de MPV e `kiosky-player`:

```text
mpv ffmpeg python3-requests
```

Nao instalar `python3-pip`, `python3-venv`, Xorg, Wayland, compositor ou Chromium nesta rodada.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts/comandos executados:

- `scripts/board/setup_totem_media_groups.sh`
- `apt-get -s install --no-upgrade --no-install-recommends mpv ffmpeg python3-requests`
- `DEBIAN_FRONTEND=noninteractive apt-get install -y --no-upgrade --no-install-recommends mpv ffmpeg python3-requests`
- `scripts/board/check_app_prereqs.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefato bruto novo da rodada:

- `totem-diag-20260429-123137-0300.tar.gz`

O pull com padrao `totem-diag-*.tar.gz` tambem copiou diagnosticos antigos ainda presentes em `/root/totem-diag`. A analise desta rodada usa o `totem-diag-20260429-123137-0300`.

Os arquivos `.tar.gz` sao evidencia bruta e nao devem ser commitados no repositorio publico. Eles podem conter IPs locais, IPv6, hostname, UUIDs do NetworkManager e logs detalhados.

## Grupos Do Usuario Totem

Antes:

```text
uid=999(totem) gid=995(totem) grupos=995(totem)
totem : totem
```

Depois:

```text
uid=999(totem) gid=995(totem) grupos=995(totem),29(audio),44(video),105(render)
totem : totem audio video render
```

O script adicionou o usuario `totem` aos grupos existentes `video`, `render` e `audio`. Nenhum grupo novo foi criado.

## Simulacao APT Antes Da Instalacao

Comando:

```text
apt-get -s install --no-upgrade --no-install-recommends mpv ffmpeg python3-requests
```

Resultado:

- 173 pacotes novos seriam instalados.
- 0 pacotes seriam atualizados.
- 0 pacotes seriam removidos.
- 7 pacotes ficariam nao atualizados.
- Nenhum pacote `linux-image`, `linux-dtb`, `linux-u-boot`, `armbian-bsp` ou `kernel` apareceu na simulacao.

A instalacao real so foi executada apos essa checagem.

## Instalacao

Comando:

```text
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-upgrade --no-install-recommends mpv ffmpeg python3-requests
```

Resultado:

- `apt-get` retornou `0`.
- 173 pacotes novos foram instalados.
- 0 pacotes foram atualizados.
- 0 pacotes foram removidos.
- Nenhum pacote `linux-image`, `linux-dtb`, `linux-u-boot`, `armbian-bsp` ou `kernel` apareceu no log da instalacao.
- Download reportado pelo APT: 111 MB.
- Uso adicional reportado pelo APT: 390 MB.

Pacotes top-level instalados:

- `mpv` `0.35.1-4`
- `ffmpeg` `7:5.1.8-0+deb12u1`
- `python3-requests` `2.28.1+dfsg-1`

O log registrou:

```text
Configurando python3-requests (2.28.1+dfsg-1)
Configurando mpv (0.35.1-4)
Configurando ffmpeg (7:5.1.8-0+deb12u1)
```

## Check App Prereqs

Resultado de `check_app_prereqs.sh`: `exit_code=1`.

Itens OK:

- `python3` encontrado em `/usr/bin/python3`.
- Modulo `venv` responde.
- `mpv` encontrado em `/usr/bin/mpv`.
- Usuario `totem` existe.
- Grupo `totem` existe.
- Diretorios persistentes em `/data` existem com ownership esperado.
- `/data/media/kiosky-player` e gravavel pelo usuario `totem`.

Avisos esperados nesta fase:

- `pip` nao encontrado.
- `/opt/totem/venv` existe, mas ainda nao tem `bin/python`.
- `/opt/totem/venv` existe, mas ainda nao tem `bin/pip`.

Falha registrada:

- `/tmp/kiosky` ausente.

Interpretacao: a falha esta relacionada a diretorio temporario em `/tmp`, nao ao pacote MPV. Como a rodada nao podia recriar diretorios alem do ajuste de grupos, o item fica pendente para a proxima etapa de preparacao/runtime ou para uma unidade systemd com `RuntimeDirectory`.

## Diagnostico Pos-Instalacao

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

- Nenhum `apt upgrade`, `full-upgrade`, `dist-upgrade` ou `armbian-upgrade` foi executado.
- `python3-pip` nao foi instalado.
- `python3-venv` nao foi instalado.
- Xorg, Wayland, compositor e Chromium nao foram instalados.
- MPV nao foi iniciado.
- `kiosk.py` nao foi iniciado.
- Nenhum servico systemd da aplicacao foi ativado.
- `deploy_kiosky_player.sh` nao foi executado.
- Nenhum commit foi feito.

## Proximos Passos

- Recriar/garantir `/tmp/kiosky` antes do teste manual, preferencialmente por script idempotente ou `RuntimeDirectory` na futura unit.
- Fazer primeiro teste manual de MPV sem iniciar o app.
- Depois, fazer deploy controlado do app e teste manual supervisionado.
- So depois avaliar unit systemd, root read-only e corte seco.
