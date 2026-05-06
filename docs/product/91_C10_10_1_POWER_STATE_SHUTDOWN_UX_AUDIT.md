# C10.10.1 - Power State / Shutdown UX Audit

Data: 2026-05-06

Status: incidente classificado como `POWER_STATE_EXPECTED_BUT_UX_UNCLEAR`.
Nao houve reboot, poweroff, writer, alteracao de config real, Wi-Fi,
NetworkManager, `kiosky-player` ou instalacao de pacotes nesta auditoria.

## Incidente

Comportamento observado pelo operador:

- apos desligamento normal, a segunda placa ficou com HDMI preto e sem SSH;
- F10/teclado nao recuperou a placa;
- remover e reconectar energia restaurou o appliance;
- apos o power cycle, a placa voltou com splash, ultima configuracao, player e
  midias normalmente.

## Auditoria Executada

Runner criado:

```bash
scripts/remote/run_c10_10_1_power_state_audit.sh
```

Modos:

- `--inspect-current`
- `--postmortem-previous-boot`
- `--classify`
- `--summary`

O runner e read-only: analisa journal em memoria e grava apenas categorias e
contadores sanitizados.

## Estado Atual

Estado sanitizado apos o power cycle:

- `kiosky-player.service=active/enabled`;
- `totem-settings-trigger.service=active/enabled`;
- `totem-open-settings.service=inactive/static`;
- `dadooh-visual-splash.service=active/enabled`;
- `NRestarts=0`;
- `systemctl_failed_count=0`;
- `kernel_critical_filter_count=0`;
- `public_state=player_running`;
- `playback=playing`;
- `player_process_count=1`;
- `mpv_process_count=1`;
- `renderer_process_count=0`;
- `setup_process_count=0`;
- `session_lock_present=false`;
- `request_present=false`;
- config real presente com permissoes `root:totem 0640`, sem leitura de
  conteudo;
- Wi-Fi dedicado presente, sem publicar SSID/conexao;
- `orientation.json` presente.

## Postmortem do Boot Anterior

Resultado sanitizado:

- `journal_previous_boot_available=true`;
- `previous_boot_shutdown_markers_present=true`;
- `previous_boot_clean_shutdown_without_reboot=true`;
- `previous_boot_had_clean_poweroff=true`;
- `previous_boot_had_reboot_marker=false`;
- `previous_boot_had_kernel_panic=false`;
- `previous_boot_had_ext4_error=false`;
- `previous_boot_had_mmc_error=false`;
- `kernel_critical_filter_count=0`;
- `ext4_error_count=0`;
- `mmc_error_count=0`;
- `previous_boot_end_category=clean_poweroff`.

Nao foram salvos logs brutos.

## Classificacao

Classificacao final:

```text
POWER_STATE_EXPECTED_BUT_UX_UNCLEAR
```

Interpretacao:

- o comportamento nao foi classificado como falha de boot;
- o estado HDMI preto/SSH indisponivel e compativel com placa desligada/halted;
- F10 e SSH nao devem funcionar depois de poweroff;
- para ligar novamente, e necessario power cycle fisico.

O installable bench RC continua valido, com follow-up obrigatorio de UX de
desligamento antes de C11/read-only:

```text
installable_bench_rc_status=valid_with_shutdown_ux_followup
```

## Politica Temporaria de Desligamento

Enquanto nao houver UX final:

- `Reiniciar totem` e a acao normal para suporte remoto/local;
- `Desligar com seguranca` deve ser protegida por confirmacao forte;
- a UI deve explicar antes do poweroff:
  `Apos desligar, sera necessario remover e reconectar a energia para ligar novamente.`;
- antes de executar poweroff, exibir por alguns segundos:
  `Desligamento seguro`;
  `Aguarde`;
  `Quando a tela apagar, remova a energia`;
- nao prometer F10, teclado ou SSH depois do poweroff;
- nao chamar poweroff de reboot.

## Proximo Passo

Proxima rodada recomendada:

```text
C10.10.2 - Shutdown UX
```

Escopo sugerido:

- localizar qualquer UI/runner que exponha desligamento;
- garantir confirmacao forte;
- adicionar tela de desligamento seguro antes do poweroff;
- documentar religamento por power cycle fisico;
- manter `Reiniciar totem` separado de `Desligar com seguranca`;
- validar sem corte seco e sem habilitar read-only.

C11.0 read-only readiness permanece bloqueado ate C10.10.2 fechar a UX de
desligamento ou confirmar que nao existe acionador de poweroff exposto ao
operador.
