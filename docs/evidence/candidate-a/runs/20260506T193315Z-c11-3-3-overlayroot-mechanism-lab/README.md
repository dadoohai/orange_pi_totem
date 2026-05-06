# C11.3.3 - Overlayroot Mechanism Lab

Data: 2026-05-06

## Escopo

Laboratorio de `overlayroot` na placa teste. A placa dev foi usada somente para
sanity check read-only e nao recebeu enablement.

## Dev Sanity

- dev_sanity_overlay_state_ok=true
- dev_kernel_critical_filter_count=2
- dev_enable_executed=false
- dev_read_only_enabled=false
- dev_overlay_active=false
- dev_overlayroot_disabled=true
- dev_experimental_patches_removed=true

## Test Lab

- test_board_used=true
- overlayroot_prereq_installed_on_test=true
- apt_dry_run_safe=true
- would_upgrade_count=0
- would_remove_count=0
- would_touch_kernel_packages=false
- kernel_packages_held=true
- test_enable_executed=true
- overlayroot_config_path=/etc/overlayroot.conf
- update_initramfs_executed=false
- reboot_executed=true
- ssh_returned=true
- overlay_active=false
- read_only_enabled=false
- root_write_blocked=false
- writable_paths_ok=true
- rollback_available=true
- rollback_executed=true
- final_test_overlayroot_disabled=true
- test_kernel_critical_filter_count=2

## Diagnostico

Depois do reboot da placa teste, o SSH voltou e os servicos estavam ativos, mas
o overlay nao ativou. A classificacao sanitizada foi:

```text
initramfs_log_driver_lookup_failed=true
```

O mecanismo oficial/package atual nao conseguiu ativar `overlayroot=tmpfs` na
placa teste, reproduzindo o bloqueio observado na dev sem arriscar a dev.

## Decisao

- ready_for_c11_3_4_enable_dev=false
- move_to_c12_image=false
- mechanism_blocked=true
- ready_for_c11_4=false

Proxima acao recomendada: investigar/fixar o mecanismo em laboratorio separado
ou trocar de abordagem. Nao tentar novo enable na dev ate uma estrategia passar
em ambiente de laboratorio.

## Guardrails

- poweroff_executed=false
- power_cut_tested=false
- writer_called=false
- real_config_read=false
- real_config_written=false
- wifi_changed=false
- networkmanager_profiles_changed=false
- raw_logs_published=false
- secrets_published=false
