# Rodada 20260429-114440 - Display/runtime probe

Status: inventario de display/runtime concluido; nenhuma instalacao ou ativacao de app foi executada.

## Objetivo

Inventariar de forma somente leitura o ambiente grafico/runtime da Orange Pi Zero 3 para decidir a proxima etapa de instalacao e teste do MPV/player.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/board/display_runtime_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos brutos copiados localmente:

- `display-runtime-20260429-114406-0300.tar.gz`
- `totem-diag-20260429-114425-0300.tar.gz`

O pull com padrao `totem-diag-*.tar.gz` tambem copiou diagnosticos antigos ainda presentes em `/root/totem-diag`. A analise desta rodada usa o `display-runtime-20260429-114406-0300` e o `totem-diag-20260429-114425-0300`.

Os arquivos `.tar.gz` sao evidencia bruta e nao devem ser commitados no repositorio publico. Eles podem conter IPs locais, IPv6, hostname, UUIDs do NetworkManager e logs detalhados.

## Sistema

- Data da coleta: `2026-04-29 11:44:06 -0300`.
- Kernel: `6.12.58-current-sunxi64`.
- Armbian: `25.11.1`, board `orangepizero3`, familia `sunxi64`.
- Target padrao do systemd: `graphical.target`.
- `systemctl --failed`: `0 loaded units listed`.

## Python

- `python3`: presente em `/usr/bin/python3`.
- Versao: `Python 3.11.2`.
- `pip3`: ausente.
- `python3 -m pip --version`: falha com `No module named pip`.
- `python3 -m venv -h`: funcional.

## Runtime De Video E Display

- `mpv`: ausente.
- `ffmpeg`: ausente.
- `Xorg`: ausente.
- `xinit`: ausente.
- `weston`: ausente.
- `cage`: ausente.
- `openbox`: ausente.
- `chromium`: ausente.

Dispositivos encontrados:

- `/dev/fb0`, grupo `video`.
- `/dev/dri/card0`, grupo `video`.
- `/dev/dri/card1`, grupo `video`.
- `/dev/dri/renderD128`, grupo `render`.

DRM/sysfs:

- Existe `card0-HDMI-A-1` apontando para `display-engine`.
- Existe `renderD128` apontando para `1800000.gpu`.
- O comando solicitado para arquivos `status` nao retornou linhas no probe.

Kernel/display:

- `sun4i-drm display-engine` inicializado.
- HDMI detectado com `EVENT=plugin` e `read_hpd result: 1`.
- `fb0` criado como framebuffer do `sun4i-drm`.
- `panfrost` inicializado para GPU `mali-g31`.
- `cedrus` registrou `/dev/video0`.

## Pacotes

Pacotes instalados relevantes pelo filtro:

- `libdrm-common`
- `libdrm2:arm64`
- `libegl-mesa0:arm64`
- `libglapi-mesa:arm64`
- `libwayland-client0:arm64`
- `libwayland-server0:arm64`

Pacotes consultados via `apt-cache policy` e nao instalados:

- `mpv`
- `ffmpeg`
- `python3-venv`
- `python3-pip`
- `python3-requests`
- `xserver-xorg`
- `xinit`
- `openbox`
- `cage`
- `weston`
- `chromium`
- `mesa-utils`
- `libdrm-tests`

Observacao: apesar de `python3-venv` aparecer como nao instalado no alvo consultado, `python3 -m venv -h` funciona nesta imagem. A criacao real do venv ainda deve ser testada em uma etapa propria.

## Usuario E Diretorios

- Usuario `totem`: existe, `uid=999`, `gid=995`.
- Grupo `totem`: existe.
- Home do usuario: `/nonexistent`.
- Shell do usuario: `/usr/sbin/nologin`.
- Grupos do usuario: somente `totem`.

Diretorios:

- `/opt/totem`: existe, `root:root`, `0755`.
- `/opt/totem/kiosky-player`: existe, `root:root`, `0755`.
- `/opt/totem/venv`: existe, `root:root`, `0755`.
- `/data/config`: existe, `totem:totem`, `0750`.
- `/data/media/kiosky-player`: existe, `totem:totem`, `0750`.
- `/data/state/kiosky-player`: existe, `totem:totem`, `0750`.
- `/data/spool/kiosky-player`: existe, `totem:totem`, `0750`.
- `/data/logs/kiosky-player`: existe, `totem:totem`, `0750`.
- `/tmp/kiosky`: ausente nesta coleta, esperado apos reboot por estar em `/tmp`.

## Kernel Critico

Nao apareceram no filtro critico:

- `oops`
- `panic`
- `EXT4-fs error`
- `Aborting journal`
- `Remounting filesystem read-only`
- `mmc.*timeout`
- `mmc.*reset`
- `voltage`

O filtro retornou mensagens conhecidas de boot com `Error applying setting, reverse things back` para UART/SPI/MMC. Nao houve falha critica observada nesta rodada.

## Recomendacao Para Proxima Etapa

Pacote minimo recomendado para a proxima rodada de instalacao controlada, sem executar agora:

```text
mpv ffmpeg python3-pip python3-requests
```

Manter `python3-venv` como dependencia explicita a considerar se a criacao real de `/opt/totem/venv` falhar ou se a imagem final preferir declarar o pacote mesmo com o modulo `venv` ja respondendo.

Como o kernel ja expoe DRM, framebuffer, HDMI e Panfrost, a primeira validacao de MPV deve tentar saida direta via DRM/KMS antes de instalar Xorg, Wayland ou compositor. Xorg/xinit/openbox ou Cage/Weston devem ficar como plano B caso MPV direto nao seja suficiente para o kiosk.

## Escopo Negativo Confirmado

- Nenhum `apt update/install/upgrade` foi executado.
- Nenhum pacote foi instalado.
- MPV nao foi iniciado.
- `kiosk.py` nao foi iniciado.
- Nenhum servico systemd da aplicacao foi ativado.
- `deploy_kiosky_player.sh` nao foi executado.
- Nenhum servico foi alterado.
