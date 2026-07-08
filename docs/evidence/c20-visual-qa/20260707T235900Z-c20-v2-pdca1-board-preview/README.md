# C20 V2 PDCA1 Board Preview

Rodada: 2026-07-07.

Objetivo: testar uma direcao visual mais forte para o wizard/settings em
`1024x768`: cards solidos, marcador retangular, rodape como acoes e campo
escuro.

Resultado operacional:

- `preview.rc=0`;
- hash do wizard original antes/depois identico;
- `kiosky-player.service=active`;
- `totem-open-settings.service=inactive`;
- sem lock/request apos a sessao.

Decisao PDCA:

- manter cards, campo escuro, paleta mais profunda e rodape de acoes;
- rejeitar o acento horizontal acima do titulo, porque na captura real ele
  cruza o texto e reduz a qualidade visual;
- seguir para PDCA2 com esse ajuste.

Non-claims:

- preview visual, nao fluxo completo por teclado;
- nao grava configuracao real;
- nao publica OTA;
- nao altera player-runtime, Wi-Fi real, display/EDID ou updater.
