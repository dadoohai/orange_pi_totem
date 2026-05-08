# C12.3.14 - Overlay Module Packaging Lab

Data: 2026-05-08

## Objetivo

Usar a placa image-lab descartavel como laboratorio runtime para testar se o
problema de read-only era apenas empacotamento do modulo `overlay` dentro do
`initramfs/uInitrd`, antes de fazer outro build completo.

Nao houve uso da dev, da placa teste antiga, writer, config real,
Wi-Fi/NetworkManager, instalacao de pacotes, poweroff ou corte seco.

## Runner

Foi criado:

```text
scripts/remote/run_c12_3_14_overlay_module_packaging_lab.sh
```

Modos principais:

- `--prepare-only`;
- `--inspect`;
- `--plan`;
- `--apply-initramfs-module-fix`;
- `--reboot-check`;
- `--collect-post-reboot`;
- `--rollback`;
- `--summary`.

As aplicacoes exigiram a confirmacao:

```text
CONFIRMO APLICAR OVERLAY MODULE PACKAGING C12.3.14
```

Os reboots exigiram a confirmacao:

```text
CONFIRMO REBOOT OVERLAY MODULE PACKAGING C12.3.14
```

## Inspect Inicial

Estado inicial da placa lab:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_fstype=ext4`;
- `overlayroot_conf_category=tmpfs`;
- `cmdline_overlayroot_tmpfs_present=true`;
- `runtime_proc_filesystems_contains_overlay=true`;
- `current_overlay_load_status=load_failed`;
- `current_modprobe_rc=0`;
- `current_insmod_rc=1`;
- `current_overlay_module_path_found=true`.

O artefato atual em `/boot/initrd.img` e o payload de `/boot/uInitrd` ja
continham:

- `overlay.ko` nao vazio;
- `modules.dep` presente;
- `modules.dep` referenciando `overlay`;
- hook fallback presente.

Isso ja indicava que a causa C12.3.13 precisava ser reclassificada: o modulo
vazio/stub nao era mais reproduzivel no estado atual da placa lab.

## H1 - manual_add_modules

Hipotese:

```text
initramfs-tools manual_add_modules overlay
```

Resultado pre-boot:

- `overlay_module_nonempty_in_initramfs=true`;
- `modules_dep_references_overlay=true`;
- `uinitrd_regenerated=true`;
- `preboot_validation_passed=true`;
- `rollback_available=true`.

Resultado apos reboot:

- `ssh_returned=true`;
- `public_state=config_missing`;
- `systemctl_failed_count=0`;
- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- root continuou `ext4`;
- `/data`, `/tmp` e `/run` continuaram gravaveis.

Rollback:

- `rollback_executed=true`;
- `update_initramfs_exit_code_bucket=zero`;
- `uinitrd_regenerated=true`.

## H2 - explicit_copy

Hipotese:

```text
copia explicita dinamica do modulo real e metadata
```

Resultado pre-boot:

- `overlay_module_nonempty_in_initramfs=true`;
- `modules_dep_references_overlay=true`;
- `uinitrd_regenerated=true`;
- `preboot_validation_passed=true`;
- `rollback_available=true`.

Resultado apos reboot:

- `ssh_returned=true`;
- `public_state=config_missing`;
- `systemctl_failed_count=0`;
- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- root continuou `ext4`;
- `/data`, `/tmp` e `/run` continuaram gravaveis.

Rollback:

- `rollback_executed=true`;
- `update_initramfs_exit_code_bucket=zero`;
- `uinitrd_regenerated=true`.

## Classificacao

C12.3.14 mostra que o ajuste de empacotamento isolado nao resolve o read-only.
Tanto H1 quanto H2 produziram um `overlay.ko` nao vazio no initramfs e
`modules.dep` coerente, mas o boot continuou com:

- `overlay_load_status=load_failed`;
- `modprobe_rc=0`;
- `insmod_rc=1`;
- `overlay_in_proc=false`;
- root `ext4` gravavel.

Classificacao atual:

```text
OVERLAY_MODULE_PACKAGING_FIXED_BUT_LOAD_STILL_FAILS
```

A classificacao C12.3.13 `OVERLAY_MODULE_EMPTY_OR_STUB_IN_INITRAMFS` fica
superada para o estado atual da placa lab. Ela foi util para direcionar o teste,
mas H1/H2 provaram que o problema restante nao e apenas modulo vazio ou
`modules.dep` ausente.

## Decisao

Nao iniciar C12.4.

Nao gerar C12.1.11 apenas repetindo a correcao de empacotamento. O proximo passo
deve diagnosticar a falha de carregamento com modulo nao vazio:

```text
C12.3.15_INITRAMFS_LOAD_FAILURE_WITH_NONEMPTY_MODULE
```

Esse diagnostico deve focar em por que `modprobe overlay` retorna zero e
`insmod overlay.ko` retorna nonzero no initramfs, mesmo com modulo real e
metadata coerente.

Atualizacao C12.3.15: o hook temporario confirmou que o modulo esta presente e
nao vazio no initramfs, mas `modprobe overlay` retorna zero sem registrar
`overlay` em `/proc/filesystems`, e `insmod overlay.ko` retorna nonzero sem
stderr/dmesg categorizavel. A classificacao atual e:

```text
INITRAMFS_MODULE_LOADING_UNSUPPORTED
```

Com isso, C12.1.11 nao deve ser iniciado como rebuild simples de empacotamento.
O proximo passo e reabrir a decisao do mecanismo read-only.

## Status

- `read_only_validated=false`;
- `ready_for_c12_4=false`;
- `ready_for_c12_1_11_rebuild=false`;
- `read_only_mechanism_still_blocked=true`;
- `next_decision_required=true`.
