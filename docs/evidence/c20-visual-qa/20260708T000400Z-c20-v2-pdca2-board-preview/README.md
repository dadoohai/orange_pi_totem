# C20 V2 PDCA2 Board Preview

Rodada: 2026-07-08.

Objetivo: validar no framebuffer real a versao candidata C20 V2, sem o acento
de titulo rejeitado no PDCA1.

Resultado operacional:

- `preview.rc=0`;
- hash do wizard original antes/depois identico;
- `kiosky-player.service=active`;
- `totem-open-settings.service=inactive`;
- sem lock/request apos a sessao.

Decisao PDCA:

- cards solidos e marcador retangular aprovados para acumulo;
- rodape de acoes aprovado para acumulo;
- campo escuro aprovado para acumulo;
- manter revisao para uma micro-iteracao de copy/decisao.

Non-claims:

- preview visual, nao fluxo completo por teclado;
- nao grava configuracao real;
- nao publica OTA;
- nao altera player-runtime, Wi-Fi real, display/EDID ou updater.
