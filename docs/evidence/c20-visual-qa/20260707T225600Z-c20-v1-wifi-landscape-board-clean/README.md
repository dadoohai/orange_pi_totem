# C20 V1 Wi-Fi Landscape Board

Rodada: 2026-07-07.

Objetivo: validar no framebuffer real a lista Wi-Fi C20 V1 em paisagem
`1024x768`, com 4 itens visiveis, rodape em uma linha e descricao menos densa.

Metodo:

- script C20 V1 instalado temporariamente na placa;
- player parado apenas durante preview read-only;
- preview Wi-Fi sintetico em `rotation_key=landscape`;
- capturas de `/dev/fb0`;
- script original restaurado e player religado ao final.

Resultado:

- `preview.rc=0`;
- hash do wizard original antes/depois identico;
- `kiosky-player.service=active`;
- `totem-open-settings.service=inactive`;
- sem lock/request apos a sessao.

Non-claims:

- usa redes sinteticas, nao Wi-Fi real;
- nao altera NetworkManager;
- nao grava configuracao real;
- nao publica OTA;
- nao altera player-runtime, display/EDID ou updater.
