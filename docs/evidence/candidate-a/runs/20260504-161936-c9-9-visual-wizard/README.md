# C9.9 Visual Wizard Validation

Data: 2026-05-04

Commit base no inicio da rodada: `e68d70f`

## Comandos

- `scripts/remote/run_c9_9_visual_wizard.sh <host> --prepare-only`
- `scripts/remote/run_c9_9_visual_wizard.sh <host> --preview-screens`
- `scripts/remote/run_c9_9_visual_wizard.sh <host> --run-cancel`
- `scripts/remote/run_c9_9_visual_wizard.sh <host> --run-complete-existing-wifi`

## Resultado

- preview visual: passou;
- cancelamento: passou;
- fluxo completo com Wi-Fi dedicado ja configurado: passou;
- candidata temporaria: gerada;
- C5.1 `--allow-mock`: passou;
- C5.1 `--real-dry-run`: falhou como esperado por placeholders;
- ajuste de teclado validado: `b/B` nao volta em campo de texto; voltar em campo usa `F2` ou `Ctrl+B`;
- renderer visual: MPV/DRM com SVG local;
- shell livre: nao observado;
- prompt Linux: nao observado.

## Estado Final

- servico: `active/enabled`;
- `NRestarts=0`;
- `public_state=player_running`;
- playback tardio: `playing`;
- player: ativo;
- MPV principal: ativo;
- renderer/setup: ausentes;
- Wi-Fi dedicado persistente: presente;
- network_changed no fluxo existente: `false`.

## Guardrails

- `real_config_read=false`;
- `real_config_written=false`;
- `writer_called=false`;
- `hotspot_created=false`;
- `portal_created=false`;
- `reboot_called=false`;
- repo `kiosky-player` nao alterado;
- config candidate bruta nao foi copiada para esta evidencia;
- logs brutos nao foram copiados para esta evidencia;
- identificadores e credenciais reais nao foram publicados.
