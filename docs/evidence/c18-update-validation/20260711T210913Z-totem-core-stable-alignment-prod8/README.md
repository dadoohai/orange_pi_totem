# C18 totem-core stable alignment for prod8

Decisao registrada em 2026-07-11 para alinhar o ponteiro stable remoto ao
`totem-core` atual da prod8.

Motivo:

- a prod8 traz
  `c21.9-prod8-pairing-restore-20260710T225825Z-665fc01`;
- o GitHub `latest` ainda oferece a stable antiga
  `c18.ota-core-prod-20260705T184013Z-ccaf5a1`;
- o updater recusou corretamente esse downgrade com `rc=45`, sem alterar a
  placa;
- a correcao deve publicar uma identidade stable estritamente nova, mantendo
  os arquivos funcionais do core C21.9 e rollback para o current existente.

Escopo autorizado:

- somente `totem-core` stable e seu auto-pull;
- imagem vinculada: `c18-hwdecode-prod-8` / `c18.image-prod.8`;
- apply, health, no-op e rollback devem ser revalidados na placa;
- nenhuma liberacao de `player-runtime`, `media-system` ou alvo futuro por
  inferencia.

Este registro autoriza a promocao; nao declara publicacao nem apply executados.

