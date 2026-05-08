# C12.3.8 - Read-only Mechanism Decision

Data: 2026-05-08

## Escopo

Diagnostico read-only da placa image-lab C12.1.8, sem nova tentativa de enable,
sem reboot, sem remount, sem writer, sem config real, sem Wi-Fi, sem instalacao
de pacotes e sem logs brutos.

Host registrado apenas como `lab_board`.

## Checks

- running_board_inspected=true
- initramfs_inspected=true
- overlayroot_script_present=true
- overlayroot_hook_started=true
- overlayroot_read_config=true
- overlayroot_mode=tmpfs
- overlay_module_present_in_initramfs=true
- modules_dep_present=true
- modules_alias_present=true
- modprobe_present=true
- force_overlay_hook_present=true
- modprobe_overlay_success=true
- mount_overlay_attempted=false
- read_only_enabled=false
- overlay_active=false
- root_write_blocked=false

## Classificacao

```text
OVERLAY_MODULE_PRESENT_BUT_NOT_REGISTERED_IN_INITRAMFS_RUNTIME
```

O `initrd`/`uInitrd` efetivo contem o hook `overlayroot`, `overlay.ko`,
`modules.dep`, `modules.alias`, `modprobe` e o hook C12.3.7. O hook roda, le o
modo `tmpfs` e tenta carregar o driver, mas `overlay` nao fica disponivel em
`/proc/filesystems` no momento em que o `overlayroot` avalia o root.

## Decisao

- decision=overlayroot_requires_deeper_initramfs_fix
- recommended_next_step=C12.3.9_FIX_INITRAMFS_MODULE_LOADING_OR_KERNEL_OVERLAY_COMPATIBILITY
- c12_4_blocked=true
- raw_logs_published=false
- secrets_published=false
