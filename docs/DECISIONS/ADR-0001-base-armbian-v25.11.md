# ADR-0001 — Base Armbian Build v25.11 para Candidato A

## Status

Aceito como primeiro candidato de bancada. Ainda não homologado para produção.

## Contexto

A Orange Pi Zero 3 aparece no Armbian como placa Community. A imagem pública associada ao kernel `6.12.23-current-sunxi64` foi considerada suspeita por relatos de `Oops` e pelo histórico observado no equipamento.

A decisão passou a considerar não só kernel, mas a composição completa:

```text
U-Boot + DRAM init + DTB + kernel + driver Wi-Fi + SD + fonte + térmica
```

## Decisão

Usar como primeiro candidato:

```text
Armbian Build v25.11
Debian Bookworm Minimal
BOARD=orangepizero3
BRANCH=current
Kernel 6.12.58-current-sunxi64
U-Boot 2025.04
NetworkManager
BSPFREEZE=yes
```

## Consequências

- Caminho limpo para a placa, sem override de `KERNEL_TARGET`.
- Evita `6.12.23-current-sunxi64`.
- Mantém stack de boot mais recente que alternativas históricas v25.02.
- Requer homologação própria antes de produção.
