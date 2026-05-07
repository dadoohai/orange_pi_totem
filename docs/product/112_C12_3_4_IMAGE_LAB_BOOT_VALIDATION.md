# C12.3.4 - Image-Lab Boot Validation

Data: 2026-05-07

## Objetivo

Validar a imagem C12.1.6 em placa de teste e classificar o comportamento
observado ao concluir o wizard e voltar para `config_missing`.

## Resultado

A imagem bootou e SSH ficou acessivel. O firstboot de laboratorio funcionou:

- `boot_success=true`;
- `ssh_available=true`;
- `firstboot_marker_present=false`;
- `lab_bootstrap_state=complete`;
- `lab_bootstrap_network_apply_attempted=true`;
- `private_firstboot_data_published=false`.

## Estado do Produto

Como a imagem-lab nao embute config real, o estado final observado foi:

- `public_state=config_missing`;
- `config_real_present=false`;
- `config_missing_visual_ok=true`;
- `stuck_starting_player=false`;
- `session.lock=false`;
- `request=false`;
- `setup_process_count=0`.

Isso e aceitavel para imagem sem config real, desde que a UI nao prometa escrita
real.

O F10 abrindo Configuracoes foi observado pelo humano durante o boot validation.
O cancelamento via F10 nao foi reexecutado por runner nesta rodada; a evidencia
disponivel apenas confirma que nao restou lock/request apos o fluxo observado.

## Candidate-Only

O wizard gerou candidata, mas nao chamou writer e nao escreveu config real:

- `visual_candidate_generated=true`;
- `apply_mode=candidate-only`;
- `writer_called=false`;
- `real_config_written=false`;
- `candidate_files_count=1`;
- `final_state=config_missing`.

Classificacao:

```text
CANDIDATE_ONLY_EXPECTED_WITHOUT_PRIVATE_VALUES
UX_AMBIGUOUS_CANDIDATE_ONLY
```

O retorno a `config_missing` e esperado sem valores privados/config real, mas a
UX deve deixar claro que a conclusao gerou apenas candidata e nao aplicou
configuracao real.

## Read-only

Read-only/overlay nao passou:

- `overlayroot.conf` contem `overlayroot="tmpfs"`;
- hook initramfs de overlayroot presente: `true`;
- script init-bottom de overlayroot presente: `true`;
- `overlay_active=false`;
- `read_only_enabled=false`;
- `root_fstype=ext4`;
- `root_write_blocked=false`;
- `/data`, `/tmp` e `/run` gravaveis: `true`;
- `journald_volatile=true`.

Classificacao principal:

```text
IMAGE_LAB_READ_ONLY_NOT_ACTIVE
```

Isso bloqueia C12.4.

## Servicos

Servicos Dadooh principais:

- `kiosky-player.service`: active/enabled;
- `totem-settings-trigger.service`: active/enabled;
- `totem-open-settings.service`: inactive/static, result success;
- `totem-firstboot-gate.service`: inactive/enabled, result success;
- `totem-lab-firstboot-autoconfig.service`: inactive/enabled, result success.

`systemctl_failed_count=1`, com falha categorizada como:

```text
console_setup
```

Nao foi tratado como blocker de produto nesta rodada, mas deve ser mantido como
observacao de imagem/base.

## Guardrails

Nao foi feito:

- writer real;
- escrita de config real;
- alteracao de Wi-Fi/NetworkManager pelo runner;
- provisionamento de secrets;
- reboot;
- poweroff;
- corte seco;
- apt upgrade/full-upgrade/dist-upgrade/armbian-upgrade.

## Decisao

C12.4 provisionamento real nao pode comecar ainda, porque a finalidade principal
da image-lab e validar root read-only/overlay e isso nao ocorreu.

Proximo passo recomendado:

```text
C12.1.7 - diagnosticar overlayroot configurado no rootfs, mas inativo no boot
```
