# C20 Claude Sonnet UX Audit Summary

Data: 2026-07-07.

Modo: auditoria externa read-only via Claude Code, modelo `sonnet`, effort
`xhigh`, sem escrita no repo e sem SSH na placa.

Veredito sintetizado:

- C19 cumpriu o escopo prometido: Wi-Fi paginado sem rodape invadido, `Esc`
  limpo e sinal ASCII sem `????`;
- a UX geral ainda esta funcional, mas nao totalmente polida;
- C20 deve fechar lacunas pequenas e visuais antes de redesign amplo.

Achado incorporado:

- ha sobreposicao visual na primeira tela de orientacao em paisagem;
- evidencia: `docs/evidence/c19-visual-qa/20260707T194848Z-wizard-navigation/01-orientation-visible.jpg`;
- prioridade recomendada: corrigir essa sobreposicao como primeira rodada C20.

Recomendacoes aceitas:

- comecar por uma correcao localizada de orientacao/preview;
- preencher melhor a tela de revisao em rodada posterior;
- investigar nitidez de fonte antes de trocar renderer ou fonte;
- simplificar card Wi-Fi somente depois da correcao de layout;
- manter SVG como auxiliar e screenshot real como evidencia decisiva.

Recomendacoes rejeitadas ou adiadas:

- redesign visual amplo imediato;
- alterar display/EDID/resolucao dentro de `totem-core`;
- Wi-Fi real persistente ou escrita real de config nesta frente;
- trocar motor de renderizacao de texto sem investigacao separada;
- qualquer mudanca em `player-runtime`, MPV ou updater.
