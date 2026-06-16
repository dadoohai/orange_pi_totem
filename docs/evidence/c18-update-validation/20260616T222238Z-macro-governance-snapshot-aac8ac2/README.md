# C18 macro governance snapshot - aac8ac2

Snapshot offline do gate macro C18 gerado em arvore limpa no commit
`aac8ac2d4272655bd1612f3c94835694d2dbb540`.

Resultado:

- schema: `dadooh.c18.ota_macro_governance_gate.v1`;
- result_claim: `c18_homologation_governance_ready_pre_h2`;
- passed: `true`;
- alvo: `player-runtime`, `channel=homologation`, `ring=pilot`;
- janela de piloto: carregada como `snapshot_only`, nao como autorizacao
  operacional atual.

Escopo:

- confirma coerencia entre H1 decisivo, readiness de piloto versionado, H2
  vermelho e diagnostico read-only;
- nao substitui H2;
- nao reabre janela de piloto expirada;
- nao autoriza producao, `stable`, auto-pull, publish ou public thaw;
- nao satisfaz soak 24h nem power-loss 17/17.

