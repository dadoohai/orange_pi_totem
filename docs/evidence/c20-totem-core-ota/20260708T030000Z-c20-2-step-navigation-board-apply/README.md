# C20.2 Totem-Core Board Apply

## Resultado

C20.2 foi aplicado na placa por `totem-updatectl apply-local` com `rc=0`.

- Pacote: `c20.2.step-navigation-20260708T022700Z-1fa33d2`
- Payload SHA256: `3700d115c801217b79ccbf6369040a954774757a2ba29cf8e1ff4157985374ae`
- Antes: `releases/c20.1.environment-copy-20260708T011500Z-7a29d1a`
- Depois: `releases/c20.2.step-navigation-20260708T022700Z-1fa33d2`
- `kiosky-player.service`: ativo antes e depois
- `totem-open-settings.service`: inativo antes e depois
- Wizard instalado: `self-test: ok`

## Evidencia Visual

Capturas reais do framebuffer da placa:

- `captures/step-menu-framebuffer.jpg`
- `captures/review-pending-framebuffer.jpg`

As capturas confirmam que o menu de etapas aparece e que a revisao parcial fica
bloqueada, sem gerar candidata incompleta.

## Escopo

Esta rodada atualiza apenas `totem-core`. Nao altera player-runtime, MPV,
midias, config de cliente, kernel, auto-pull ou stable.
