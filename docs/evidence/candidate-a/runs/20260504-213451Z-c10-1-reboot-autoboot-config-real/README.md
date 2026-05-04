# C10.1 - Reboot/Autoboot com Config Real

Data: 2026-05-04

Commit base: `5eaabdd`

## Comandos

- `scripts/remote/run_c10_1_reboot_autoboot_config_real.sh <host> --prepare-only`
- `scripts/remote/run_c10_1_reboot_autoboot_config_real.sh <host> --preflight`
- `scripts/remote/run_c10_1_reboot_autoboot_config_real.sh <host> --reboot-autoboot`

## Preflight

- servico: `active/enabled`;
- `NRestarts`: `0`;
- `public_state`: `player_running`;
- playback: `playing`;
- player: ativo;
- MPV: ativo;
- renderer: ausente;
- setup: ausente;
- Wi-Fi dedicado presente: sim;
- config real presente: sim;
- permissoes da config: `root:totem` `0640`;
- usuario `totem` le: sim;
- usuario `totem` escreve: nao;
- `systemctl --failed`: 0;
- filtro critico de kernel: 0.

## Reboot

- reboot executado: sim;
- confirmacao humana: `CONFIRMO REBOOT CONTROLADO C10.1`;
- tempo ate SSH voltar: 46 segundos;
- convergencia aguardada: sim;
- convergiu para player: sim.

## Estado Final

- servico: `active/enabled`;
- `NRestarts`: `0`;
- `public_state`: `player_running`;
- playback: `playing`;
- player: ativo;
- MPV: ativo;
- renderer: ausente;
- setup: ausente;
- Wi-Fi dedicado presente: sim;
- config permissions ok: sim;
- usuario `totem` le: sim;
- usuario `totem` escreve: nao;
- `systemctl --failed`: 0;
- filtro critico de kernel: 0.

## Guardrails

- config real publicada: nao;
- backup publicado: nao;
- valores privados publicados: nao;
- environment_id real publicado: nao;
- identificadores de rede publicados: nao;
- logs brutos publicados: nao;
- config real lida: nao;
- config real escrita: nao;
- writer chamado: nao;
- Wi-Fi alterado: nao;
- NetworkManager alterado: nao;
- hotspot criado: nao;
- portal criado: nao;
- repo `kiosky-player` alterado: nao;
- root read-only habilitado: nao;
- corte seco executado: nao.

## Read-only Readiness

- `read_only_not_enabled=true`;
- `power_cut_not_tested=true`;
- NetworkManager/perfil Wi-Fi precisam de politica para root read-only;
- logs/journald precisam de politica;
- `/var/lib` e `/etc` precisam de auditoria;
- cache/config em `/data` seguem no caminho esperado;
- runtime em `/tmp` segue no caminho esperado.

## Observacao

O `wizard_rc=8` observado em C10.0 fica classificado como retorno bruto de
wrapper TTY nao bloqueante para boot/autoboot. C10.1 validou que o sistema sobe
sozinho com config real e player operacional.

## Proximos Passos

- C10.2: fluxo `config_missing` real controlado.
- C11.0: auditoria de readiness para root read-only antes de qualquer corte
  seco.
