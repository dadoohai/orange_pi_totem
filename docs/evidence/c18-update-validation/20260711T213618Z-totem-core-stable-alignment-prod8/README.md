# Prod8 totem-core stable alignment

Resultado: a falta imediata do timer de `totem-core` foi corrigida.

## Problema observado

A imagem `c18-hwdecode-prod-8` trazia o core C21.9, mas o `latest` remoto ainda
apontava para o pacote C18 antigo. A cada janela, o updater protegia a placa e
recusava o downgrade com `rc=45`; nada regredia, mas o serviço ficava failed
até ser limpo.

## Correção

Foi publicada a release stable
`totem-core-c21.10-prod8-stable-alignment-20260711T211510Z-ff7810c`.
O conteúdo funcional extraído é byte-idêntico ao C21.9 embutido na prod8; a
nova identidade e o timestamp apenas alinham o canal remoto à imagem já
distribuída. O payload continua restrito a `totem-core`.

Antes da publicação:

- gate global: `78/78`, árvore limpa;
- gate de promoção stable: verde, sem blockers;
- duas auditorias independentes xhigh: zero blockers;
- pacote e plano de publicação auditados separadamente.

## Prova pública e de placa

- release pública, não draft e não prerelease;
- seis assets baixados novamente e hashes iguais aos artefatos validados;
- nova release confirmada como `latest`;
- serviço público `totem-update-agent.service` aplicou C21.10 com `rc=0`;
- segunda invocação foi no-op: state, current e previous não mudaram;
- rollback governado voltou para C21.9 com `rc=0`;
- nova invocação pública restaurou C21.10 com C21.9 em previous;
- self-test do core passou em todas as fases;
- C23 permaneceu current, player ativo, zero restarts, um MPV e freeze público
  de `player-runtime` em `rc=44`;
- estado final sem units failed.

O HDMI estava desconectado nesta operação. O status vivo continuou `playing`,
mas esta rodada não reivindica inspeção visual da saída HDMI; isso não é
necessário para provar o alinhamento do pacote `totem-core`.

## Arquivos

- `c21-10-pre.json`: estado anterior e registro do `rc=45` antigo;
- `c21-10-post-apply.json`: primeira aplicação pública;
- `c21-10-noop.json`: segunda invocação sem alteração;
- `c21-10-rollback.json`: retorno governado para C21.9;
- `c21-10-restored.json`: estado final restaurado em C21.10;
- `c21-10-github-release.json`: metadados e seis assets publicados;
- `c21-10-github-release-list.json`: C21.10 como `latest`;
- `c21-10-remote-assets.sha256`: hashes dos assets baixados do GitHub;
- `c21-10-production-timer-evidence-gate.json`: gate offline verde do roundtrip;
- `operation-summary.json`: resumo executável da decisão e do roundtrip.
