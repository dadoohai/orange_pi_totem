# C10.5.3 - Early Boot Visual Leak Audit

Status: validado em bancada com reboot controlado.

Data: 2026-05-05

## Objetivo

Auditar e reduzir o texto tecnico que ainda pode aparecer antes do splash de
produto assumir a HDMI no inicio do boot.

## O Que Ainda Aparecia

Apos C10.5.2, o humano observou uma janela curta com texto tecnico tipo
Armbian/fsck, incluindo contagem de `files`/`blocks`, antes do splash Dadooh
`Inicializando`.

## Runner

Arquivo:

```bash
scripts/remote/run_c10_5_3_early_boot_visual_audit.sh
```

Modos:

- `--prepare-only`;
- `--inspect`;
- `--plan`;
- `--apply-reversible-boot-quiet`;
- `--rollback-reversible-boot-quiet`;
- `--reboot-visual-check`.

O runner nao publica logs brutos, cmdline completa, config real, dados de rede
ou identificadores privados.

## Inspecao

`--inspect` coleta apenas categorias:

- existencia de `/boot/armbianEnv.txt`;
- categoria de `verbosity`;
- categoria de `console`;
- flags allowlisted em `extraargs` e cmdline atual;
- gettys visiveis;
- servicos visuais;
- estado de rollback C10.5.2/C10.5.3;
- estado operacional do player.

## Plano Reversivel

`--plan` nao aplica nada. Ele pode propor, se o arquivo de boot for reconhecido:

- `verbosity=0`;
- `console=serial`;
- `quiet`;
- `loglevel=0`;
- `systemd.show_status=false`;
- `rd.systemd.show_status=false`;
- `vt.global_cursor_default=0`;
- `logo.nologo`.

C10.5.3 nao desabilita fsck, nao altera initramfs e nao remove rollback.

## Resultado

Inspecao inicial:

- `/boot/armbianEnv.txt` reconhecido;
- console Armbian em categoria `both`;
- verbosity em categoria `normal`;
- gettys visiveis inativos;
- splash e player ativos;
- `systemctl_failed_count=0`.

Aplicacao:

- backup criado com permissao restrita;
- rollback registrado em `/data/state/totem-boot-visual/`;
- console passou para categoria `serial`;
- verbosity passou para categoria `quiet`;
- `loglevel=0`, `rd.systemd.show_status=false` e `logo.nologo` ficaram
  presentes;
- fsck nao foi desabilitado.

Reboot visual:

- SSH voltou em `8s`;
- servico final `active/enabled`;
- `NRestarts=0`;
- `public_state=player_running`;
- playback `playing`;
- player/MPV ativos e renderer/setup ausentes;
- `systemctl_failed_count=0`;
- `kernel_critical_filter_count=0`;
- observacao humana: o texto tecnico early-boot sumiu.

## Aplicacao

`--apply-reversible-boot-quiet` exige:

```text
CONFIRMO EARLY BOOT QUIET C10.5.3
```

Ele faz backup restrito de `/boot/armbianEnv.txt`, grava estado de rollback em
`/data/state/totem-boot-visual/` e nao reboota automaticamente.

Rollback exige:

```text
CONFIRMO ROLLBACK EARLY BOOT QUIET C10.5.3
```

Reboot visual exige:

```text
CONFIRMO REBOOT VISUAL EARLY BOOT C10.5.3
```

## Fora do Corte

- sem root read-only;
- sem corte seco;
- sem writer;
- sem config real;
- sem Wi-Fi/NetworkManager;
- sem `kiosky-player`;
- sem hotspot/portal/backend;
- sem imagem final.

## Proximo Passo

C10.6 - Modo Manutencao Local V0, depois que a politica de boot visual ficar
validada ou a limitacao remanescente for aceita.
