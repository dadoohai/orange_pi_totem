# C10.5.2 - Visual Guard + Boot/Shutdown Guardrails

Status: validado tecnicamente com reboot controlado; observacao humana visual
pos-reboot ainda deve ser registrada.

Data: 2026-05-05

## Objetivo

Reduzir a chance de a HDMI cair para Armbian, login, shell ou texto tecnico em
boot, shutdown e transicoes entre player, wizard e splash.

## Display Owner

Estados permitidos para o operador:

- `boot_splash`;
- `transition_splash`;
- `wizard`;
- `player`;
- `shutdown_splash`.

Estados proibidos na HDMI de produto:

- login/getty;
- shell;
- console Armbian;
- mensagens systemd/kernel visiveis;
- tela preta com texto tecnico.

O runner C10.5.2 sempre tenta renderizar splash de transicao antes de parar o
player e pausa temporariamente o getty da TTY de produto nos testes que tomam a
HDMI.

## Implementado

- `totem_visual_splash.py` agora le `/data/state/totem-display/orientation.json`
  quando `--rotation-deg` nao e informado;
- o wizard visual pode gravar esse contrato publico allowlisted com
  `--write-public-orientation`;
- o arquivo publico contem somente `schema_version`, `updated_at`,
  `rotation_deg` e `orientation_label`;
- novo runner `run_c10_5_2_visual_guard_boot_shutdown.sh` com:
  - `--prepare-only`;
  - `--inspect`;
  - `--preview-transition-splash`;
  - `--apply-visual-guardrails`;
  - `--rollback-visual-guardrails`;
  - `--reboot-visual-check`;
  - `--transition-stress-short`.

## Guardrails Persistentes

Aplicacao persistente exige:

```text
CONFIRMO GUARDRAILS VISUAIS BOOT C10.5.2
```

Rollback exige:

```text
CONFIRMO ROLLBACK GUARDRAILS VISUAIS BOOT C10.5.2
```

Reboot visual exige:

```text
CONFIRMO REBOOT VISUAL C10.5.2
```

Os guardrails continuam reversiveis: backup de boot args quando usados, estado
dos gettys preservado e servico de splash restauravel.

## Fora do Corte

- sem read-only;
- sem corte seco;
- sem writer;
- sem alteracao de config real;
- sem alteracao de Wi-Fi/NetworkManager;
- sem hotspot/portal/backend;
- sem alteracao no `kiosky-player`.

## Validacao

Comandos esperados:

```bash
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --prepare-only
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --inspect
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --preview-transition-splash
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --apply-visual-guardrails
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --transition-stress-short
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --reboot-visual-check
```

Modos que pausam a HDMI/player exigem:

```text
CONFIRMO C10.5.2 VISUAL GUARD COM PAUSA DO PLAYER
```

Resultado de bancada:

- `--prepare-only`: passou;
- `--inspect`: passou e identificou `getty@tty2` ativo antes dos guardrails;
- `--preview-transition-splash`: passou;
- `--transition-stress-short`: passou;
- `--apply-visual-guardrails`: passou com rollback state presente;
- `--reboot-visual-check`: reboot executado; SSH voltou; snapshot final
  sanitizado passou;
- estado final `active/enabled`, `NRestarts=0`, `public_state=player_running`,
  playback `playing`, player/MPV ativos e renderer/setup ausentes;
- `systemctl --failed` ficou em `0`;
- config real, writer e Wi-Fi nao foram tocados.

O runner herdado C10.5 encerrou cedo durante a coleta pos-reboot quando a porta
SSH ainda resetava conexoes. C10.5.2 registra isso como falso negativo de coleta
e corrige o runner para tentar novamente antes de falhar.

Observacao humana: ainda apareceu rapidamente texto tecnico tipo Armbian/fsck
com `files`/`blocks` no inicio do boot, antes do splash Dadooh `Inicializando`.
As transicoes ja ficam cobertas por splash, mas a janela muito cedo de boot
permanece como limitacao documentada. C10.5.2 nao desabilita fsck nem altera
initramfs; esse refinamento fica para a trilha de imagem/read-only/boot inicial.

## Proximo Passo

C10.6 deve iniciar o Modo Manutencao Local V0 depois que os guardrails visuais
persistentes estiverem validados em reboot controlado.
