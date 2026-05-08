# C12.3.9 - Initramfs Overlay Module Diagnostics

Data: 2026-05-08

## Escopo

Diagnostico controlado na placa image-lab, registrada apenas como `lab_board`.
Nao houve uso da dev, da placa teste antiga, writer, config real, Wi-Fi,
NetworkManager, instalacao de pacotes, poweroff, corte seco ou logs brutos.

## Execucao

- diagnostic_hook_installed=true
- backup_created=true
- rollback_available=true
- update_initramfs_returncode=0
- uinitrd_nonempty_after=true
- reboot_executed=true
- ssh_returned=true
- diagnostic_collected=true
- rollback_executed=true
- diagnostic_hook_present_after=false

## Diagnostico Sanitizado

- proc_mounted=true
- overlay_in_proc_before=false
- modprobe_present=true
- insmod_present=true
- overlay_ko_exists=false
- modules_dep_exists=true
- vermagic_match=unknown
- module_path_match=false
- modprobe_overlay_result=zero
- overlay_in_proc_after_modprobe=false
- insmod_overlay_attempted=false
- insmod_overlay_result=missing
- overlay_in_proc_after_insmod=false
- mount_overlay_test_attempted=false

## Estado Pos-reboot

- read_only_enabled=false
- overlay_active=false
- root_write_blocked=false
- data_writable=true
- tmp_writable=true
- run_writable=true
- public_state=config_missing
- systemctl_failed_count=0

## Classificacao

```text
OVERLAY_MODULE_PATH_INVALID
```

O hook roda com `/proc` disponivel e `modprobe overlay` retorna zero, mas o
arquivo `overlay.ko` nao esta visivel no caminho de modulo esperado dentro do
runtime do initramfs. Sem `overlay.ko` resolvido, `insmod` nao e tentado e
`overlay` continua ausente de `/proc/filesystems`.

## Proximo Passo

```text
C12.1.9_REBUILD_WITH_INITRAMFS_MODULE_PATH_FIX
```

O rebuild deve corrigir o layout/caminho dos modulos no initramfs efetivo antes
do `overlayroot`, sem trocar ainda para outro mecanismo e sem iniciar C12.4.

## Guardrails

- raw_logs_published=false
- secrets_published=false
- config_real_published=false
- wifi_changed=false
- writer_called=false
