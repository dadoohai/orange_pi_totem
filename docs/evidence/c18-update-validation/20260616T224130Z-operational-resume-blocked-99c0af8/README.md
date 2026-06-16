# C18 operational resume blocked - 99c0af8

Snapshot offline do gate de retomada operacional gerado no commit
`99c0af8b07e552cb1c5beff999b467f2f6628070`.

Resultado:

- schema: `dadooh.c18.ota_operational_resume_gate.v1`;
- result_claim: `c18_operational_resume_blocked`;
- passed: `false`.

Motivos esperados:

- `current_pilot_authorization:authorization_window_expired`;
- `current_board_preflight:preflight_stale`;
- `current_board_preflight:preflight_stage_mismatch`.

Escopo:

- confirma que o snapshot macro verde nao e autorizacao operacional viva;
- confirma que a autorizacao de 2026-06-12/13 nao pode ser reutilizada em
  2026-06-16;
- confirma que o preflight antigo `post_apply_observation` nao substitui um
  preflight fresco `pre_apply`;
- nao executa SSH, nao coleta placa, nao aplica, nao publica, nao promove
  `stable`, nao abre thaw e nao substitui H2.

