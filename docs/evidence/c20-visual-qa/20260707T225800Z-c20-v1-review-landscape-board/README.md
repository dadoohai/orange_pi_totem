# C20 V1 Review Landscape Board

Rodada: 2026-07-07.

Objetivo: validar no framebuffer real a tela de revisao C20 V1 em paisagem,
com resumo publico no corpo principal e painel lateral limitado a orientacoes
curtas.

Metodo:

- script C20 V1 instalado temporariamente na placa;
- player parado apenas durante preview read-only;
- tela de revisao gerada em `layout_rotation_deg=0`;
- capturas de `/dev/fb0`;
- script original restaurado e player religado ao final.

Resultado:

- `preview.rc=0`;
- hash do wizard original antes/depois identico;
- `kiosky-player.service=active`;
- `totem-open-settings.service=inactive`;
- sem lock/request apos a sessao.

Leitura visual:

- `captures/fb-*.png` sao capturas brutas do framebuffer e podem abrir
  transparentes em alguns viewers;
- `captures/fb-*-visible.jpg` sao as versoes para revisao humana.

Non-claims:

- nao valida salvamento real;
- nao grava configuracao real;
- nao publica OTA;
- nao altera player-runtime, Wi-Fi real, display/EDID ou updater.
