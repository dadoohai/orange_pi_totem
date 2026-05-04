# C9.9 - Wizard Visual Local

Status: implementado e validado em bancada com HDMI/teclado.

Data: 2026-05-04

## Objetivo

Trocar a experiencia TTY/ASCII validada em C9.8 por uma camada visual local de
produto no proprio totem, ainda sem writer, config real, hotspot ou portal.

## Implementado

- novo `scripts/board/totem_setup_visual_wizard.py`;
- telas SVG privadas em `/tmp/dadooh-c9-9-visual-wizard/screens`;
- exibicao via MPV/DRM, sem desktop, Chromium, Xorg, Wayland ou compositor;
- entrada por teclado local, sem shell livre;
- fluxo com Boas-vindas, Conexao, Ambiente, Tela, Revisao e Concluir;
- opcao para usar Wi-Fi dedicado ja configurado pelo C9.8;
- opcao para reconfigurar Wi-Fi persistente usando o adapter C9.8;
- candidata C5.1 em `/tmp`, com backend/API ainda mock;
- runner remoto `scripts/remote/run_c9_9_visual_wizard.sh`.

## Aparencia Para Operador

O operador ve telas Dadooh com titulo grande, indicador de etapas, blocos de
acao e instrucoes curtas de teclado. O terminal continua existindo apenas como
canal tecnico por baixo do `openvt`, mas nao deve aparecer como prompt ou shell.

## Guardrails

- nao le `/data/config/config.json`;
- nao escreve `/data/config/config.json`;
- nao chama writer;
- nao altera o `kiosky-player`;
- pausa o player somente no runner, para tomar a HDMI, e restaura ao final;
- nao cria hotspot ou portal;
- nao publica identificadores de rede, credenciais, environment_id real, logs
  brutos ou payloads.

## Validacao

Localmente:

- `python3 scripts/board/totem_setup_visual_wizard.py --self-test`;
- `python3 scripts/board/totem_setup_visual_wizard.py --preview-screens`;
- `python3 scripts/board/totem_setup_visual_wizard.py --scripted`;
- C5.1 `--allow-mock` passa para a candidata;
- C5.1 `--real-dry-run` falha como esperado por placeholders.

Em bancada:

- `scripts/remote/run_c9_9_visual_wizard.sh <host> --prepare-only`;
- `scripts/remote/run_c9_9_visual_wizard.sh <host> --preview-screens`;
- `scripts/remote/run_c9_9_visual_wizard.sh <host> --run-cancel`;
- `scripts/remote/run_c9_9_visual_wizard.sh <host> --run-complete-existing-wifi`.

Resultado validado:

- telas visuais Dadooh apareceram sem shell livre;
- cancelamento funcionou;
- fluxo completo com Wi-Fi dedicado ja configurado gerou candidata;
- C5.1 `--allow-mock` passou;
- C5.1 `--real-dry-run` falhou como esperado por placeholders;
- servico final `active/enabled`, `NRestarts=0`, `public_state=player_running`,
  playback `playing`, player/MPV ativos e renderer/setup ausentes.

## Continua Fora

- QR funcional;
- portal local;
- hotspot;
- backend/login;
- writer real;
- escrita da config real;
- reboot automatico.

## Proximo Passo

C10.0 deve ligar o wizard visual ao writer real controlado, com escrita de
config real e partida do player somente depois de validacao explicita.
