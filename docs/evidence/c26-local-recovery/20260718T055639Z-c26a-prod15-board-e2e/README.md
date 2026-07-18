# C26A na prod15: apply, rollback e reapply

Escopo: provar na placa de bancada que o motor C26A, ainda invisivel, pode ser
instalado sobre a `prod15`, revertido para C21.24 e reaplicado sem expor as
acoes que dependem da imagem sucessora.

## Identidade

- C26A: `c26.3-local-recovery-20260718-d0363b7`
- manifest SHA-256: `6dfcc58871ef166df2dc83a59682a0062550a816b332f30d1ebcdb80d3205b24`
- payload SHA-256: `58c3c12cd9aa777cec320147143b8401e6800dff392179c32356ff384f65f026`
- imagem da placa: `c18-hwdecode-prod-15`

## Resultado

| Momento | Current | Previous |
| --- | --- | --- |
| Antes | C21.24 | vazio |
| Apos apply | C26A | C21.24 |
| Apos rollback | C21.24 | C26A |
| Final, apos reapply | C26A | C21.24 |

- a politica `stable` bloqueou o manifesto `homologation` com `rc=41` antes
  de qualquer mutacao;
- o apply, rollback e reapply governados retornaram `rc=0`;
- C26A declara somente `product-reset-v1`; a `prod15` nao possui o comando de
  contrato de imagem C26, portanto as acoes permanecem escondidas;
- a politica final voltou byte-identica ao inicio, SHA-256
  `6d0fb46a8401ac1b6df8d733fc5210209824927159ca918711323fe3d5e0bd4f`;
- no fechamento ao vivo: timer `enabled/active`, agente `inactive`, player
  `active`, `NRestarts=0`.

Os `status.*.json` sao copias JSON validas; os arquivos `status.*.raw.txt`
preservam a saida original do transporte SSH. Nenhuma credencial foi
registrada.

## Limites

Esta evidencia nao prova C26B, imagem sucessora, UX visual, HDMI, playback
profundo ou producao. Ela autoriza apenas manter C26A invisivel e avancar para
a regravacao controlada da candidata.
