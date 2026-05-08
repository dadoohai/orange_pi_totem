# C12.3.7 Overlay Module Initramfs Lab

Data: 2026-05-08

## Resultado

- image_version=c12.1.8
- lab_board_used=true
- h1_executed=true
- h1_result=failed
- h2_executed=true
- h2_result=failed
- overlay_module_in_initramfs=true
- overlay_module_in_uinitrd=true
- force_overlay_hook_in_initramfs=true
- overlay_active=false
- read_only_enabled=false
- root_write_blocked=false
- writable_paths_ok=true
- ssh_returned_after_reboots=true
- systemctl_failed_count=0
- winning_hypothesis=none
- rollback_available=true
- next_build_fix=not_ready_simple_rebuild
- read_only_mechanism_still_blocked=true
- next_decision_required=true

## Guardrails

- writer_called=false
- real_config_written=false
- wifi_changed=false
- packages_installed=false
- poweroff_executed=false
- raw_logs_published=false
- secrets_published=false

## Classificacao

```text
OVERLAY_DRIVER_UNAVAILABLE_IN_INITRAMFS_RUNTIME
```

Forcar `overlay` em `/etc/initramfs-tools/modules` e adicionar hook de
`modprobe overlay` antes do `overlayroot` nao ativou root read-only/overlay.
C12.4 continua bloqueado.
