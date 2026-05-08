# C12.3.17 - Boot Validate Overlayfs Built-in

Data: 2026-05-08

## Escopo

Validacao de boot real da imagem C12.1.12 com `overlayroot` e
`CONFIG_OVERLAY_FS=y` built-in no kernel.

Imagem esperada:

```text
Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-12_minimal.img
```

## Resultado

```text
image_version=c12.1.12
board_booted=true
ssh_available=true
c12_3_17_status=blocked
c12_3_17_failure_category=IMAGE_LAB_READ_ONLY_NOT_ACTIVE_WITH_BUILTIN_OVERLAYFS
```

A primeira tentativa de SSH nao autenticou com chave. Depois, com senha usada
apenas interativamente e sem publicar valor, o inspect remoto foi executado.

## Validacao Read-only

O kernel em execucao tem overlayfs built-in e o parametro `overlayroot=tmpfs`
chega ao boot, mas o root continua montado como `ext4` em device fisico.

```text
kernel_overlayfs_builtin_running=true
overlay_in_proc_filesystems=true
cmdline_overlayroot_present=true
cmdline_overlayroot_tmpfs_present=true
overlayroot_config_detected=true
overlayroot_tmpfs_detected=true
overlayroot_cfgdisk_category=disabled
root_mount_type=ext4
root_mount_source_category=device
overlay_active=false
root_test_file_created=false
root_test_file_persisted_after_reboot=false
root_test_write_nonpersistent=false
data_test_file_created=false
data_test_file_persisted_after_reboot=false
data_test_write_persistent=false
data_writable=true
tmp_writable=true
run_writable=true
journald_storage_category=volatile
journald_volatile=false
networkmanager_active=true
systemctl_failed_count=1
systemctl_failed_categories=console_setup
readonly_semantics_valid=false
```

Nenhum marcador sintetico foi criado e nenhum reboot foi executado, porque o
inspect inicial confirmado retornou `overlay_active=false`.

Estado de produto sanitizado:

```text
public_state=config_missing
playback=unknown
config_real_present=false
```

## Guardrails

```text
controlled_reboot_executed=false
poweroff_executed=false
power_cut_tested=false
apt_update_executed=false
apt_upgrade_executed=false
writer_called=false
secrets_published=false
ready_for_c12_4=false
c12_4_blocked=true
```

## Proximo Passo

Diagnosticar por que `overlayroot=tmpfs` e `CONFIG_OVERLAY_FS=y` estao presentes
em runtime, mas o root ainda monta como `ext4`. O proximo passo deve focar em
`overlayroot`/initramfs/boot flow, nao em driver `overlay.ko` modular.

Proibicoes mantidas: sem senha SSH, IP/MAC/DNS, SSID/senha, conteudo de
`firstboot.conf`, API key, API URL real, `environment_id`, config real, tokens,
logs brutos ou midia/cache.
