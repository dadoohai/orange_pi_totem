# Rodada 20260429-011015 - Candidato A

Status: aprovado para a coleta de diagnostico desta rodada. O Candidato A ainda nao esta homologado para producao.

## Identificacao

| Item | Valor |
| --- | --- |
| Data/hora local | 2026-04-29 01:10 America/Sao_Paulo |
| Host usado | `root@192.168.18.114` |
| Imagem | Armbian Build v25.11 / Debian Bookworm Minimal |
| Kernel esperado | `6.12.58-current-sunxi64` |
| U-Boot esperado | `2025.04` |
| Politica | `BSPFREEZE=yes`, sem upgrade amplo |

## Scripts executados

- `scripts/board/collect_diag.sh`
- `scripts/board/network_snapshot.sh`
- `scripts/remote/pull_artifacts.sh`

## Artefatos brutos

Arquivos copiados para este diretorio, mantidos apenas para auditoria local:

- `totem-diag-20260429-010955-0300.tar.gz`
- `network-snapshot-20260429-011002-0300.tar.gz`

Esses arquivos nao sao versionaveis/publicaveis neste repositorio publico. Eles podem conter endereco de rede local, IPv6 completo, hostname, UUIDs do NetworkManager, nomes de conexao e SSID real.

## Resumo tecnico sanitizado

- Resultado geral: aprovado.
- `systemctl --failed`: `0 loaded units listed`.
- Kernel tainted: `1024`, observado e esperado nesta fase de validacao da base.
- Pacotes criticos Armbian em hold:
  - `armbian-bsp-cli-orangepizero3-current`
  - `linux-dtb-current-sunxi64`
  - `linux-image-current-sunxi64`
  - `linux-u-boot-orangepizero3-current`
- Outros pacotes em hold observados:
  - `armbian-firmware`
  - `base-files`
- Ethernet: `end0` conectada em rede local privada.
- Wi-Fi: `wlan0` presente, desconectado/dormant.
- `rfkill`: Wi-Fi e Bluetooth sem bloqueio.
- Bluetooth: sem ocorrencia `Bluetooth: hci0` no filtro critico desta coleta.

## Itens criticos ausentes

- `Internal error: Oops`
- `kernel panic`
- `EXT4-fs error`
- `Aborting journal`
- `Remounting filesystem read-only`
- `mmc timeout/reset`
- `systemctl --failed` diferente de zero

## Observacoes

O filtro amplo de kernel ainda registrou mensagens de boot `Error applying setting, reverse things back` associadas a UART/SPI/MMC. Nesta rodada elas nao vieram acompanhadas de Oops, panic, erro EXT4, remount read-only ou timeout/reset de MMC.

Recomendacao: nao commitar os `.tar.gz` brutos no repositorio publico. Para publicacao, usar somente resumos sanitizados como este README ou evidencias redigidas.
