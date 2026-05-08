# C12.1.9 - Rebuild Image-Lab Overlay Module Path

Data: 2026-05-08

## Escopo

Rebuild local da imagem-lab. Nenhuma placa foi tocada, nenhum cartao foi
gravado, nenhum writer foi chamado, nenhuma config real foi provisionada e
nenhum dado sensivel foi publicado.

## Artefato

- image_version=c12.1.9
- image_path=/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-9_minimal.img
- sha256=f581ffab591462b1daa60a648f0ed0f8c2831deff9004f9ff16cdaa46fd11e6c
- build_success=true
- card_written=false
- boards_touched=false

## Causa Anterior

- cause_from_c12_3_9=OVERLAY_MODULE_PATH_INVALID

O diagnostico C12.3.9 mostrou que o hook do initramfs tinha `modprobe`,
`insmod` e `modules.dep`, mas nao resolvia `overlay.ko` pelo caminho esperado
no runtime do initramfs.

## Fix Aplicado

- fix_applied=overlay_module_effective_path_resolution
- boot_args_overlayroot_tmpfs=true
- overlay_load_hook_included=true
- overlay_load_hook_uses_effective_path=true
- initramfs_lib_symlink_to_usr_lib=true
- uinitrd_lib_symlink_to_usr_lib=true

A imagem C12.1.9 preserva o layout usr-merged do initramfs, onde `/lib` aponta
para `usr/lib`. A validacao agora trata `/lib/modules/...` como caminho efetivo
quando o symlink existe e o modulo esta presente em `usr/lib/modules/...`.

## Validacao Offline

- overlayroot_included=true
- initrd_img_exists=true
- uinitrd_exists=true
- uinitrd_nonempty=true
- uinitrd_payload_matches_initrd_img=true
- initrd_contains_overlayroot_hook=true
- uinitrd_contains_overlayroot_hook=true
- overlay_module_effective_path_present=true
- overlay_module_usr_path_present=true
- modules_dep_effective_path_present=true
- modules_alias_effective_path_present=true
- modules_dep_references_overlay=true
- modprobe_present_in_initramfs=true
- insmod_present_in_initramfs=true
- effective_boot_initramfs_overlay_resolvable=true
- effective_boot_initramfs_valid=true
- firstboot_autoconfig_valid=true
- secret_scan_result=pass
- ready_for_card_write=true

## Guardrails

- secrets_published=false
- firstboot_conf_contents_published=false
- config_real_included=false
- wifi_or_networkmanager_changed=false
- writer_called=false
- final_image=false

## Proximo Passo

- ready_for_c12_2_5_card_write=true
- c12_4_blocked=true

C12.2.5 deve gravar a imagem C12.1.9 em cartao de teste e C12.3.x deve validar
se o boot ativa `read_only_enabled=true`, `overlay_active=true` e
`root_write_blocked=true`.
