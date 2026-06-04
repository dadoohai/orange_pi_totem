# Diagnostico Operacional E Incidentes De Campo

Este documento e o ponto central para diagnosticos operacionais que atravessam
varias frentes do produto e nao pertencem exclusivamente ao contrato OTA.

Use este arquivo quando a pergunta for: "o aparelho parece vivo, mas algo no
campo nao esta funcionando como esperado?". Para regras de update, usar
`UPDATE_CONTRACT.md`. Para readiness OTA C18, usar
`docs/product/189_C18_OTA_READINESS_GATE.md`.

## Principio

Nem todo problema visivel na tela e regressao de player, OTA ou MPV. A
investigacao deve separar pelo menos quatro camadas:

1. `player/decode`: app, MPV, hwdecode, frames e transicoes.
2. `scanout`: DRM/KMS, CRTC, planes, framebuffer e modo ativo.
3. `link/sink`: HDMI HPD, EDID, clocks de display e comportamento da TV/monitor.
4. `operacao`: energia, cabo, fonte, display desligado/travado, rede e suporte.

O deep-health C18 cobre principalmente `player/decode`. Ele e necessario para
seguranca de OTA de player, mas nao prova sozinho que o painel fisico esta
emitindo luz.

## Caso De Referencia: C18 Display Blackout

Incidente: tela preta apos evento de energia, com SSH e player vivos.

Classificacao final: `sink_hung_board_healthy`.

Evidencia:

- board com uptime continuo;
- `kiosky-player` ativo e `NRestarts=0`;
- mesmo processo MPV vivo;
- MPV usando HW decode e frames avancando;
- KMS com CRTC ativo e plane cobrindo o modo ativo;
- clocks HDMI/TCON ativos no rate do modo;
- video recuperado ao ciclar energia apenas da TV/display, sem reboot nem
  restart do board.

Registro duravel:

- `docs/evidence/c18-display-blackout/README.md`;
- `docs/evidence/c18-display-blackout/20260604-tv-sink-hang-conclusion.md`;
- `docs/evidence/c18-display-blackout/20260604-tv-power-cycle-evidence.txt`.

Conclusao operacional: nao reiniciar automaticamente o board para essa classe.
O board pode estar transmitindo corretamente e o sink/display pode estar travado.
O recovery conhecido foi power-cycle do display/sink.

## Diagnostico Futuro Recomendado

Criar um collector read-only de display/HDMI, idealmente em `totem-core`, para
classificar:

- `display_ok`: playback, scanout e sink coerentes.
- `sink_hung_board_healthy`: player/scanout saudaveis, mas sink suspeito.
- `pipeline_stalled`: player ou scanout parados com sink presente.
- `no_sink`: HDMI/EDID/HPD ausente.

Sinais uteis:

- MPV IPC e sidecars de deep-health;
- service status e restart counters;
- connector status, enabled, DPMS, EDID hash e modo ativo;
- `/sys/kernel/debug/dri/*/state` filtrado para CRTC/plane/fb;
- `clk_summary` para branch HDMI/TCON;
- contagem/rate de eventos HPD com uptime monotonic e boot id.

Evitar:

- confiar em `tmds_char_rate=0` como prova de HDMI morto neste BSP;
- reboot automatico do board quando a assinatura aponta para sink travado;
- loops agressivos de DPMS/modeset sem prova de seguranca;
- capturar framebuffer bruto, midias, URLs, config real ou dados sensiveis.

## Relacao Com OTA

Este incidente nao bloqueia a trilha OTA C18. Ele informa backlog de diagnostico
e suporte de campo. Mudancas em display/HDMI, MPV/hwdecode, kernel, systemd ou
player-runtime continuam fora do OTA comum de `totem-core` e exigem imagem,
homologacao ou pacote C18-aware explicitamente aprovado.
