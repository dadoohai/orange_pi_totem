# C19.3 Signal ASCII Validation Attempt

Data: 2026-07-07.

Objetivo: validar a lista Wi-Fi real apos trocar o indicador de sinal para
ASCII.

Resultado: nao decisivo.

O fluxo navegou pelo wizard e restaurou o player corretamente, mas o screenshot
capturado (`wifi-signal-visible.jpg`) mostrou a tela de orientacao, nao a lista
Wi-Fi. Esta pasta deve ser lida como tentativa operacional, nao como prova
visual do indicador.

Sinais uteis:

- `session-status-final.json` terminou com `setup_cancelled=true`;
- `real_config_written=false`;
- `wifi_changed=false`;
- player restaurado.

Evidencia decisiva posterior:

- `../20260707T203245Z-signal-ascii-preview-burst/`.
