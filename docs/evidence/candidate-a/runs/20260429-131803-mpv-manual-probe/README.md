# Rodada 20260429-131803 - MPV manual probe

Status: teste manual de MPV concluido sem iniciar `kiosk.py`, sem deploy do app e sem alterar systemd da aplicacao.

## Objetivo

Executar o primeiro teste manual de MPV na base minima atual da Orange Pi Zero 3, sem app e sem systemd da aplicacao, para verificar se o MPV consegue decodificar e exibir midia local usando saida direta DRM/KMS antes de considerar Xorg, Wayland ou compositor.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/mpv_manual_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos brutos principais:

- `mpv-manual-20260429-132802-0300.tar.gz`
- `totem-diag-20260429-132923-0300.tar.gz`

Observacao: a primeira tentativa `mpv-manual-20260429-131604-0300.tar.gz` registrou timeout na geracao inicial da midia. O script foi ajustado para usar `ffmpeg -nostdin`, duracao no filtro `lavfi` e timeout maior na geracao. Os resultados abaixo usam a tentativa corrigida `mpv-manual-20260429-132802-0300`.

O pull com padroes amplos tambem copiou diagnosticos antigos ainda presentes em `/root/totem-diag`. A analise desta rodada usa o artefato MPV `20260429-132802-0300` e o diagnostico `20260429-132923-0300`.

Os arquivos `.tar.gz` sao evidencia bruta e nao devem ser commitados no repositorio publico.

## Ambiente

- `mpv`: `0.35.1`.
- `ffmpeg`: `5.1.8-0+deb12u1`.
- Usuario `totem`: pertence aos grupos `totem`, `audio`, `video` e `render`.
- Dispositivos observados: `/dev/fb0`, `/dev/dri/card0`, `/dev/dri/card1`, `/dev/dri/renderD128`.
- `systemctl --failed` antes e depois do probe: `0 loaded units listed`.

## Midia Gerada

Midia local gerada sem rede:

```text
/tmp/kiosky/mpv-probe/testsrc-5s.mp4
```

Caracteristicas registradas:

- Fonte: `lavfi/testsrc`.
- Duracao: 5 segundos.
- Resolucao: `640x360`.
- Codec: H.264 via `libx264`, perfil Constrained Baseline.
- Tamanho final: 56 KiB.
- Owner final: `totem:totem`, modo `0640`.

## Resultados MPV

| Teste | Modo | Usuario | Exit code | Resultado |
| --- | --- | --- | --- | --- |
| A | `--vo=null --ao=null --frames=120` | root | 0 | Aprovado; MPV decodificou a midia. |
| B | `--vo=drm --profile=sw-fast --ao=null --fs` | root | 0 | Aprovado; MPV usou `VO: [drm]`. |
| C | `--vo=gpu --gpu-context=drm --hwdec=auto-safe --ao=null --fs` | root | 0 | Aprovado; MPV usou `VO: [gpu]`. |
| D | `--vo=drm --profile=sw-fast --ao=null --fs` | totem | 0 | Aprovado; MPV usou `VO: [drm]` como `totem`. |
| E | `--vo=gpu --gpu-context=drm --hwdec=auto-safe --ao=null --fs` | totem | 0 | Aprovado; MPV usou `VO: [gpu]` como `totem`. |

Mensagens observadas sem falha do comando:

- Nos testes DRM/GPU apareceu `VT_GETMODE failed: Inappropriate ioctl for device` e aviso de que terminal switching ficaria indisponivel. Interpretacao: limitacao esperada do contexto via SSH/pseudo-terminal, nao falha do teste nesta rodada.
- Nos testes GPU apareceu tentativa de carregar CUDA (`Cannot load libcuda.so.1`) por causa de `--hwdec=auto-safe`; o MPV continuou e retornou `0`.

## Kernel E Servicos

- Nao houve `Oops`, `panic`, `EXT4-fs error`, `Aborting journal`, `Remounting filesystem read-only`, `mmc timeout/reset` ou alerta de `voltage` no filtro critico.
- O filtro critico ainda mostrou mensagens conhecidas de boot com `Error applying setting, reverse things back` para UART/SPI/MMC.
- `systemctl --failed` permaneceu em `0 loaded units listed`.

## Observacao Humana

Video fisicamente visivel na tela: pendente de confirmacao humana.

Os exit codes indicam que os modos DRM/KMS e GPU/DRM completaram com sucesso, mas esta rodada nao deve ser interpretada como confirmacao visual fisica sem observacao do operador.

## Escopo Negativo Confirmado

- Nenhum comando `apt` foi executado.
- Nenhum pacote foi instalado.
- Xorg, Wayland, compositor e Chromium nao foram instalados.
- `kiosk.py` nao foi iniciado.
- O app nao foi deployado.
- Nenhum servico systemd da aplicacao foi instalado, habilitado ou iniciado.
- Nenhum root read-only ou teste de corte seco foi executado.
- Nenhum commit foi feito.

## Recomendacao

Seguir com DRM/KMS como caminho provavel para a proxima etapa, preferencialmente validando primeiro a observacao humana de video na tela e depois um teste manual controlado do player/app usando o usuario `totem`.

Nao ha indicacao nesta rodada para instalar Xorg, Wayland ou compositor. Manter essas opcoes como plano B somente se testes reais do player exigirem.
