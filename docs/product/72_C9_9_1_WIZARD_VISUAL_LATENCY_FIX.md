# C9.9.1 - Correcao de Latencia do Wizard Visual

Status: implementado e validado em bancada com HDMI/teclado.

Data: 2026-05-04

## Objetivo

Diagnosticar e corrigir o atraso visual observado no C9.9, onde a tela parecia
ficar um evento atrasada: caractere, Backspace e Enter so apareciam ou tinham
efeito visual no input seguinte.

## Diagnostico

Foi criado um probe isolado com telas sinteticas:

- `scripts/board/totem_visual_render_latency_probe.py`;
- `scripts/remote/run_c9_9_1_visual_latency_probe.sh`.

O probe pausou o player apenas para tomar a HDMI, nao tocou Wi-Fi, nao leu ou
escreveu config real, nao chamou writer e nao salvou screenshot bruta. A causa
provavel foi classificada como `mpv_ipc_load_not_presenting_immediately`: o
estado do wizard e os comandos MPV estavam corretos, mas o caminho visual
`gpu+drm` nao apresentava SVG estatico de forma imediata no HDMI.

O caminho `vo=drm` com MPV reiniciado por tela respondeu no primeiro input, mas
produziu flash para a TTY/shell entre teclas. O caminho MPV via IPC evitava o
flash, mas voltou a ficar um input atrasado. Ambos ficaram como diagnostico,
nao como solucao final.

## Correcao

O wizard visual passou a usar um renderer direto no framebuffer (`/dev/fb0`)
com fonte PSF ja instalada no sistema. Ele continua gerando SVGs privados em
`/tmp` como evidencia e usa a mesma estrutura visual, mas apresenta a tela
diretamente no framebuffer durante o fluxo interativo.

O modo MPV continua disponivel apenas para diagnostico/fallback por variaveis:

- padrao: `TOTEM_VISUAL_WIZARD_RENDERER=framebuffer`;
- fallback diagnostico: `TOTEM_VISUAL_WIZARD_RENDERER=mpv`;
- modo MPV diagnostico: `TOTEM_VISUAL_WIZARD_MPV_VIDEO_MODE=drm` ou `gpu_drm`.

Tambem foi corrigido o tratamento de teclas especiais: `Esc` sozinho continua
cancelando, mas sequencias como `PgUp`/`PgDn` nao sao mais tratadas como
cancelamento acidental.

## Validado

- probe automatico e manual C9.9.1;
- `framebuffer_svg` mostrou caracteres digitados e respondeu no primeiro input
  observado pelo operador;
- o flash para shell/TTY durante a digitacao deixou de ocorrer no fluxo aceito;
- `python3 scripts/board/totem_setup_visual_wizard.py --self-test`;
- `python3 scripts/board/totem_visual_render_latency_probe.py --self-test`;
- `python3 scripts/board/totem_config_contract_validate.py --self-test`;
- `bash -n` dos runners alterados;
- `git diff --check`;
- C9.9 `--run-cancel`;
- C9.9 `--run-complete-existing-wifi`;
- C5.1 `--allow-mock` passou;
- C5.1 `--real-dry-run` falhou como esperado por placeholders.

Estado final validado: servico `active/enabled`, `NRestarts=0`,
`public_state=player_running`, playback `playing`, player/MPV ativos e setup
ausente.

## Fora do Escopo

- writer real;
- escrita de `/data/config/config.json`;
- alteracao de Wi-Fi;
- hotspot;
- portal;
- QR funcional;
- backend/login;
- alteracao do `kiosky-player`;
- reboot.

## Proximo Passo

C10.0 pode seguir para wizard visual responsivo com writer real controlado,
config real e partida do player, ainda com confirmacoes explicitas e evidencia
sanitizada.
