# C12.1.10 - Rebuild Image-Lab Overlay Dynamic Path

Data: 2026-05-08

## Scope

- cause_from_c12_3_11=OVERLAY_MODULE_PATH_MISMATCH
- fix_applied=dynamic_overlay_module_path_resolution
- boards_touched=false
- card_written=false
- final_image=false
- writer_called=false
- real_config_embedded=false
- wifi_changed=false
- raw_logs_published=false

## Artifact

- build_success=true
- image_version=c12.1.10
- image_path=/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-10_minimal.img
- sha256=c7e3e2af5e2cfa52db0a1cb73141b941a239471940020953d6debfbb0133e4b2
- package_manifest_created=true
- integration_manifest_created=true
- rootfs_validation_created=true

## Offline Validation

- overlayroot_included=true
- uinitrd_nonempty=true
- uinitrd_payload_matches_initrd_img=true
- boot_script_uses_uinitrd=true
- overlay_module_discoverable_in_initramfs=true
- overlay_module_discovery_method=static
- fallback_hook_dynamic_path=true
- modules_dep_references_overlay=true
- modprobe_present_in_initramfs=true
- insmod_present_in_initramfs=true
- effective_boot_initramfs_overlay_resolvable=true
- effective_boot_initramfs_valid=true
- firstboot_autoconfig_valid=true
- secret_scan_result=pass
- ready_for_card_write=true

## Next

- ready_for_c12_2_6_card_write=true
- c12_4_blocked=true

No secrets, private firstboot contents, config real, SSID, password, IP/MAC/DNS
or raw logs were published.
