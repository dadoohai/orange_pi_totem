# C12.3.10 - Boot Validate C12.1.9

Data: 2026-05-08

## Escopo

Validacao de boot real da image-lab C12.1.9 na placa registrada apenas como
`lab_board`. Nenhuma dev foi tocada, nenhuma placa teste antiga foi tocada,
nenhum wizard foi aberto, nenhum writer foi chamado, nenhuma config real foi
provisionada, nenhum pacote foi instalado, nenhum reboot/poweroff foi executado
e nenhum log bruto foi publicado.

## Artefato

- image_version=c12.1.9
- image_version_confirmed=true
- sha256_confirmed=true
- sha256=f581ffab591462b1daa60a648f0ed0f8c2831deff9004f9ff16cdaa46fd11e6c
- ssh_available=true
- firstboot_lab_complete=true

## Produto

- public_state=config_missing
- config_real_present=false
- config_missing_visual_ok=true
- shell_seen=unknown
- kiosky-player.service=active/enabled
- totem-settings-trigger.service=active/enabled
- totem-open-settings.service=inactive/static
- totem-firstboot-gate.service=inactive/enabled
- systemctl_failed_count=1
- systemctl_failed_category=console_setup

## Read-only

- read_only_enabled=false
- overlay_active=false
- root_write_blocked=false
- root_fstype=ext4
- root_mount_options_category=rw_or_unknown
- data_writable=true
- tmp_writable=true
- run_writable=true
- journald_volatile=true

## Diagnostico Sanitizado

- cmdline_overlayroot_tmpfs_present=true
- armbian_env_overlayroot_tmpfs_present=true
- boot_script_uses_uInitrd=true
- uInitrd_payload_extracted=true
- overlayroot_hook_present=true
- overlay_load_hook_present=true
- overlayroot_hook_ran=true
- overlayroot_mode_tmpfs_detected=true
- overlay_module_present_in_initramfs=true
- overlay_module_effective_path_present=true
- modules_dep_references_overlay=true
- modprobe_overlay_attempted=true
- modprobe_overlay_result=zero
- insmod_fallback_attempted=true
- insmod_fallback_result=nonzero
- overlay_appears_in_proc_filesystems_after_boot=true
- overlay_mount_attempted=false

## Classificacao

```text
INSMOD_FALLBACK_FAILED
```

C12.1.9 corrigiu o problema anterior de caminho: o hook encontra o modulo no
initramfs efetivo. A falha atual ocorre depois disso: o fallback `insmod` roda,
mas retorna nonzero no runtime do initramfs. O driver `overlay` aparece em
`/proc/filesystems` depois do boot normal, mas tarde demais para o
`overlayroot`.

## Status

- ready_for_c12_4=false
- next_step=C12.3.11_INITRAMFS_INSMOD_FAILURE_DIAGNOSTICS

## Guardrails

- raw_logs_published=false
- secrets_published=false
- config_real_published=false
- wifi_changed=false
- writer_called=false
- poweroff_executed=false
- reboot_executed=false
