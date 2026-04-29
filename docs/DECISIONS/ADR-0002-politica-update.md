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
