# ADR-0003 — Root read-only e /data persistente

## Status

Planejado.

## Contexto

O produto opera em totens sujeitos a corte de energia. Root filesystem gravável em microSD aumenta risco de corrupção EXT4, initramfs e falha de boot.

## Decisão planejada

Separar:

```text
/              root protegido/read-only com overlay
/opt/totem     aplicação instalada
/data/config   configuração persistente
/data/media    mídias baixadas
/data/spool    telemetria pendente
/tmp           tmpfs
/var/log       zram/RAM ou log reduzido
```

## Consequências

- Corte seco deve preservar o sistema base.
- Escritas persistentes ficam concentradas em `/data`.
- Downloads precisam ser atômicos (`.tmp` + validação + rename).
- Teste de corte seco só deve ocorrer depois dessa arquitetura estar pronta.
