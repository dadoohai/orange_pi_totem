# C10.5.1 - Orientation UX Contract

Status: validado em bancada com HDMI/teclado.

Data: 2026-05-05

## Objetivo

Corrigir o contrato de orientacao do wizard visual sem rotacionar um bitmap
pronto. A UI deve navegar por setas, confirmar/cancelar a orientacao e seguir
em layout nativo de paisagem ou retrato, sem deformar textos.

## Implementado

- etapa Orientacao usa setas como caminho principal, com Enter para visualizar;
- atalhos numericos continuam apenas como fallback secundario;
- confirmacao usa lista com `Usar esta orientacao` e `Voltar e escolher outra`;
- telas seguintes passam a ser geradas em canvas nativo:
  - paisagem: `1280x720`;
  - retrato: `720x1280`;
- o renderer de framebuffer passa a mapear o canvas logico para o framebuffer
  preservando proporcao de texto;
- o wizard grava `orientation.json` publico/sanitizado no out-dir temporario;
- `setup-status.json`, `summary.txt` e candidata continuam registrando
  `rotation_deg` sem publicar dados sensiveis;
- `totem_visual_splash.py` aceita `--rotation-deg` e renderiza splash em
  paisagem/retrato pelo mesmo contrato.

## Contrato

`orientation.json` contem somente:

- `schema_version`;
- `updated_at`;
- `rotation_deg`;
- `orientation_label`;
- `layout_mode`;
- flags publicas de seguranca.

Ele nao contem API, ambiente, SSID, senha, IP, MAC, DNS, config ou logs. O
contrato para midias/player continua sendo `config.rotation_deg`, preservado no
handoff e no writer validado nas rodadas C10.

## Fora do Corte

- nao aplica read-only;
- nao executa corte seco;
- nao altera Wi-Fi/NetworkManager;
- nao chama writer;
- nao escreve config real;
- nao altera `kiosky-player`;
- nao instala desktop, Chromium, Xorg, Wayland ou compositor.

## Validacao

Comandos locais executados:

```bash
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
bash -n scripts/remote/run_c10_5_1_orientation_ux_contract.sh
```

Runner remoto:

```bash
scripts/remote/run_c10_5_1_orientation_ux_contract.sh <board-host> --prepare-only
scripts/remote/run_c10_5_1_orientation_ux_contract.sh <board-host> --preview-orientation-flow
scripts/remote/run_c10_5_1_orientation_ux_contract.sh <board-host> --run-complete-portrait
scripts/remote/run_c10_5_1_orientation_ux_contract.sh <board-host> --run-complete-landscape
scripts/remote/run_c10_5_1_orientation_ux_contract.sh <board-host> --preview-splash-orientations
```

Modos que tomam HDMI/TTY exigem confirmacao humana:
`CONFIRMO C10.5.1 ORIENTATION UX COM PAUSA DO PLAYER`.

Resultado em bancada:

- `--prepare-only`: passou;
- `--preview-orientation-flow`: passou;
- `--run-complete-portrait`: passou com `rotation_deg=270`;
- `--run-complete-landscape`: passou com `rotation_deg=180`;
- `--preview-splash-orientations`: passou para `0`, `90`, `180` e `270`;
- C5.1 `allow-mock`: passou nos fluxos com candidata;
- C5.1 `real-dry-run`: falhou como esperado por placeholders;
- servico final `active/enabled`, `NRestarts=0`;
- `public_state=player_running`, playback `playing`;
- player/MPV ativos, renderer/setup ausentes.

## Proximo Passo

C10.5.2 deve aplicar guardrails visuais persistentes de boot/shutdown de forma
reversivel, com reboot controlado e rollback.
