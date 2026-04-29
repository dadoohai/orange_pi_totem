# Rodada 20260429-121613 - Runtime APT sim

Status: simulacao de instalacao concluida; nenhum pacote foi instalado.

## Objetivo

Simular a instalacao minima de runtime para MPV/player na Orange Pi Zero 3, sem executar instalacao real, sem iniciar MPV, sem iniciar `kiosk.py` e sem alterar servicos.

## Comandos Remotos Executados

Host usado: `root@[ip-local-redigido]`

```text
apt-get -s install --no-upgrade --no-install-recommends mpv ffmpeg python3-requests
apt-get -s install --no-upgrade --no-install-recommends mpv ffmpeg python3-requests python3-venv
apt-cache policy mpv ffmpeg python3-requests python3-venv python3-pip
```

Saidas brutas locais:

- `raw/apt-sim-minimal.txt`
- `raw/apt-sim-with-venv.txt`
- `raw/apt-cache-policy.txt`
- `raw/packages-minimal.txt`
- `raw/packages-with-venv.txt`
- `raw/packages-added-by-venv.txt`

## Resultado Da Simulacao

Sem `python3-venv`:

- 173 pacotes novos seriam instalados.
- 0 pacotes seriam atualizados.
- 0 pacotes seriam removidos.
- 7 pacotes ficariam nao atualizados.
- Nenhum pacote `linux-image`, `linux-dtb`, `linux-u-boot`, `armbian-bsp` ou `kernel` apareceu na transacao simulada.

Com `python3-venv`:

- 179 pacotes novos seriam instalados.
- 0 pacotes seriam atualizados.
- 0 pacotes seriam removidos.
- 7 pacotes ficariam nao atualizados.
- Nenhum pacote `linux-image`, `linux-dtb`, `linux-u-boot`, `armbian-bsp` ou `kernel` apareceu na transacao simulada.

Pacotes top-level confirmados pela simulacao minima:

- `mpv`
- `ffmpeg`
- `python3-requests`

Pacotes top-level/pacotes de suporte adicionados ao incluir `python3-venv`:

- `python3-distutils`
- `python3-lib2to3`
- `python3-pip-whl`
- `python3-setuptools-whl`
- `python3-venv`
- `python3.11-venv`

## Pacotes Disponiveis

`apt-cache policy` mostrou candidatos disponiveis e nao instalados:

- `mpv`: `0.35.1-4`
- `ffmpeg`: `7:5.1.8-0+deb12u1`
- `python3-requests`: `2.28.1+dfsg-1`
- `python3-venv`: `3.11.2-1+b1`
- `python3-pip`: `23.0.1+dfsg-1`

## Analise

A simulacao com `--no-upgrade --no-install-recommends` nao tenta atualizar nem remover pacotes, e nao toca em kernel ou pacotes Armbian criticos. O volume de dependencias e alto porque `mpv` e `ffmpeg` puxam pilha de codecs, fontes, Mesa/GL, SDL, VA/VDPAU, X11 common e bibliotecas multimidia. Isso e esperado para MPV/FFmpeg mesmo sem Xorg completo ou compositor.

Incluir `python3-venv` adiciona apenas seis pacotes sobre a simulacao minima. Ele nao instala o pacote `python3-pip` como comando global, mas adiciona wheels de pip/setuptools para bootstrapping de venv. Como o probe anterior mostrou `python3 -m venv -h` funcionando, a necessidade real de `python3-venv` deve ser decidida no teste de criacao do venv, nao antes.

`python3-pip` nao parece necessario para a primeira bancada se a dependencia Python do player for atendida por `python3-requests` via APT e o teste manual usar Python do sistema. Evitar `python3-pip` por enquanto reduz superficie mutavel e evita misturar PyPI com a base validada antes de haver uma estrategia de wheelhouse/venv controlada.

## Recomendacao

Pacote minimo para primeiro teste de MPV:

```text
mpv ffmpeg
```

Pacote minimo para primeiro teste manual do `kiosky-player`:

```text
mpv ffmpeg python3-requests
```

Nao incluir `python3-pip` por enquanto. Incluir `python3-venv` somente se a proxima rodada exigir criar `/opt/totem/venv` com pip interno, ou se a imagem final decidir declarar venv explicitamente mesmo com `python3 -m venv -h` respondendo hoje.

Na bancada, parece seguro executar posteriormente um `apt install` especifico com `--no-upgrade --no-install-recommends` para os pacotes acima, porque a simulacao nao apontou atualizacoes, remocoes ou pacotes de kernel/Armbian. Ainda assim, antes da instalacao real, repetir a simulacao imediatamente e abortar se aparecer qualquer update/remove ou pacote `linux-*`, `armbian-*` ou `kernel`.

## Escopo Negativo Confirmado

- Nenhum `apt install` real foi executado.
- Nenhum `apt upgrade`, `full-upgrade`, `dist-upgrade` ou `armbian-upgrade` foi executado.
- Nenhum pacote foi instalado.
- MPV nao foi iniciado.
- `kiosk.py` nao foi iniciado.
- Nenhum servico foi alterado.
- Nenhum commit foi feito.
