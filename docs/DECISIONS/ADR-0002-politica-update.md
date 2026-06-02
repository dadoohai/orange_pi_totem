# ADR-0002 — Política de atualização controlada

## Status

Aceito.

## Decisão

Proibir `apt upgrade`, `apt full-upgrade`, `apt dist-upgrade` e `armbian-upgrade` em campo.

## Justificativa

A estabilidade depende da composição validada de kernel, DTB, U-Boot e BSP. Atualização livre pode trocar componentes críticos e invalidar a homologação.

## Permitido

- `apt update`;
- `apt-get install --no-upgrade -y <pacote>` em bancada;
- atualização de app por release versionada com rollback;
- atualização de mídia/configuração via backend em `/data`.

## Adendo C18 — OTA manual-first

Para a linha C18, o OTA permitido no curto prazo é **manual/operator-triggered**
e restrito ao componente `totem-core` (wizard, splash, status, Wi-Fi adapter e
helpers sob `/data/core/totem`, com fallback em `/opt/totem/core-fallback`).

`kiosky-player`, MPV e a stack `hwdecode` ficam congelados fora do OTA enquanto
não existir um pacote explicitamente C18-aware e homologado. Correções nesses
componentes seguem por nova imagem ou por uma rodada de pacote própria, com
validação de playback/hwdecode.

O timer de auto-pull não deve nascer habilitado nas imagens C18. Reativar
atualização automática é uma decisão posterior, condicionada a hardening de
operação não assistida (recuperação de apply interrompido, checagem de espaço,
retenção/GC de releases e gates de promoção).
