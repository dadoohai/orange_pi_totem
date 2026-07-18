# Auditoria independente C26A

Modelo auditor: GPT-5.6 Terra, `xhigh`, leitura independente e sem SSH.

Veredito: **nao-blocker** para manter C26A atual e gravar a candidata em uma
unica placa de bancada. Nao e veredito de producao.

Confirmado pelo auditor:

- hashes dos pacotes C26A e C26B;
- gate C26B registrado com 85/85 no commit `a6dac35`;
- contrato C26 atual com 16/16;
- transicao C26A `apply -> rollback -> reapply` e alternancia correta de
  `current/previous`;
- restauracao byte-identica da politica stable;
- C26A sem `totem-actions-v1` e acoes escondidas na prod15.

Limites apontados:

- o gate 85/85 antecede os dois ajustes exclusivos do gerador de imagem; o
  contrato C26 16/16 cobre o HEAD posterior;
- nao havia deep-health de playback pos-reapply;
- C26B e a imagem sucessora ainda precisavam da prova fisica;
- os arquivos raw tinham trailer do transporte; copias JSON validas foram
  geradas sem substituir os raw.

Correcao do decisor central: na saida final, o terceiro estado `active` era o
player, nao o agente OTA. A verificacao posterior confirmou explicitamente:
timer `enabled/active`, agente `inactive`, player `active`, `NRestarts=0`.
