# C19 Totem-Core Apply/Rollback Evidence

Data: 2026-07-07.

Pacote validado:
`c19.visual-settings-20260707T205630Z-5df93c1`.

Escopo:

- aplicar localmente o pacote `totem-core` de homologacao C19;
- validar health/self-test;
- validar playback curto apos apply e apos rollback;
- voltar a placa ao estado inicial.

Resultado:

- `apply-local --component totem-core`: passou;
- `current` apos apply: `c19.visual-settings-20260707T205630Z-5df93c1`;
- `rollback --component totem-core`: passou;
- `current` apos rollback: `c18.ota-core-prod-20260705T184013Z-ccaf5a1`;
- restauracao final: `current=c18.ota-core-prod-20260705T184013Z-ccaf5a1`,
  `previous=c17.6-environment-input-20260514T211247Z`;
- policy final: `stable`, `allow_prerelease=false`;
- timer final: `active` e `enabled`;
- `kiosky-player.service`: `active`;
- playback deep-health curto: passou apos apply e apos rollback.

Controle de risco:

- o timer foi pausado antes da policy temporaria;
- `totem-update-agent.service` foi checado como inativo;
- policy `homologation` foi temporaria e restaurada no final;
- o release C19 aplicado na placa foi removido no cleanup;
- `state.json`, `current` e `previous` foram restaurados ao estado inicial.

Nao-claims:

- nao publica C19;
- nao promove C19 para `stable`;
- nao valida Wi-Fi real/persistente;
- nao corrige display/EDID/resolucao;
- nao altera `player-runtime`, `media-system`, kernel ou updater.
