# C20 V1 Layout Preview Board

Rodada: 2026-07-07.

Objetivo: validar no framebuffer real que o wizard C20 V1 ocupa melhor o modo
paisagem `1024x768`, sem reintroduzir sobreposicao na orientacao.

Metodo:

- script C20 V1 instalado temporariamente na placa;
- `totem_open_settings_session.sh` em modo `preview`;
- capturas de `/dev/fb0` durante a sessao;
- script original restaurado ao final.

Resultado:

- `session.rc=0`;
- hash do wizard original antes/depois identico;
- `kiosky-player.service=active`;
- `totem-open-settings.service=inactive`;
- sem lock/request apos a sessao.

Leitura visual:

- `captures/fb-*.png` sao capturas brutas do framebuffer e podem abrir
  transparentes em alguns viewers;
- `captures/fb-*-visible.jpg` sao as versoes para revisao humana.

Non-claims:

- nao valida fluxo completo por teclado;
- nao grava configuracao real;
- nao publica OTA;
- nao altera player-runtime, Wi-Fi real, display/EDID ou updater.
