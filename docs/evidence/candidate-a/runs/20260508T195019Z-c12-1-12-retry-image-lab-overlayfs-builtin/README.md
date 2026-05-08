# C12.1.12 Retry Image-lab Overlayfs Built-in

Data: 2026-05-08

## Host Diagnosis

- wsl2_detected: `true`;
- host_memory_available: `approximately_8_7GiB`;
- host_swap_available: `approximately_2_9GiB`;
- docker_memory_limit_detected: `approximately_9_668GiB`;
- active_build_containers_before_retry: `false`;
- disk_space_ok: `true`;
- probable_cause_previous_failure: `rootfs_apt_memory_pressure_transient`.

## Kernel Reuse

- previous_attempt: `c12.1.11`;
- previous_failure: `BUILD_HOST_CHROOT_APT_MEMORY_ERROR`;
- kernel_deb_reusable: `true`;
- kernel_reused: `true`;
- kernel_rebuild_executed: `false`;
- kernel_overlayfs_builtin: `true`;
- CONFIG_OVERLAY_FS_y: `true`;
- CONFIG_OVERLAY_FS_m_absent: `true`;

Kernel artifact hashes:

- linux-image:
  `098b9ad49ebb74ad88d2fe2249bbbd11d8c79845fbae5124c68fa7699f6988ad`;
- linux-dtb:
  `062d5d6a94a0fde5deb75b9da574d9fe25eeb657e9a0b9118e168c06015a5060`;
- linux-headers:
  `83d543f071183ac5026b9a999c0bc2258d15a632d4f1a1018f65d3a526bdfcf5`;
- linux-u-boot:
  `88d0cdf065b337fee50121f36dc354fa311349d6b32b1feccc7d5e9811102a3e`.

## Build Result

- build_success: `true`;
- image_built: `true`;
- image_version: `c12.1.12`;
- image_path:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-12_minimal.img`;
- sha256:
  `1220aab2272b5e6fa3430b6aab1c180624441104ab6b4ab7a1a1932fc8373a81`;
- build_log:
  `/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-11f9d2a0-3176-437f-b039-f98bd02ef1fc.log`;
- package_manifest:
  `/tmp/dadooh-c12-1-image-lab-readonly/20260508T191500Z-c12-1-build-image-lab-readonly/package-manifest.txt`;
- integration_manifest:
  `/tmp/dadooh-c12-1-image-lab-readonly/20260508T191500Z-c12-1-build-image-lab-readonly/read-only-integration-manifest.txt`.

## Offline Validation

- artifact_validation: `ok`;
- checksum_ok: `true`;
- overlayroot_included: `true`;
- overlayroot_tmpfs_configured: `true`;
- kernel_config_overlayfs_builtin: `true`;
- rootfs_kernel_config_overlayfs_builtin: `true`;
- overlay_module_required: `false`;
- overlayfs_builtin_expected: `true`;
- initrd_contains_overlayroot_hook: `true`;
- uinitrd_exists: `true`;
- uinitrd_nonempty: `true`;
- uinitrd_payload_matches_initrd_img: `true`;
- effective_boot_initramfs_valid: `true`;
- modular_overlay_fallback_hooks_present: `false`;
- diagnostic_initramfs_hooks_present: `false`;
- ready_for_c12_2_7_card_write: `true`;
- ready_for_c12_3_boot_ssh_validation: `true`.

## Firstboot Lab

- lab_firstboot_mode: `private_disposable_lab`;
- artifact_private: `true`;
- final_image: `false`;
- firstboot_conf_committed: `false`;
- firstboot_conf_contents_published: `false`;
- require_manual_firstboot: `false`.

The private firstboot file contents were not printed or copied into evidence.

## Guardrails

- card_written: `false`;
- boards_touched: `false`;
- ssh_used: `false`;
- writer_called: `false`;
- real_config_included: `false`;
- secrets_published: `false`;
- raw_logs_published: `false`;
- c12_4_blocked: `true`.

## Decision

C12.2.7 card write can begin with the C12.1.12 image. C12.4 remains blocked
until a real boot validates overlayroot persistence semantics.
