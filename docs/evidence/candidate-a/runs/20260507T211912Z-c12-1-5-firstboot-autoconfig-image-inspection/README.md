# C12.1.5 - Firstboot Autoconfig Image Inspection

Data: 2026-05-07

## Escopo

- placas tocadas: `false`
- cartao gravado: `false`
- config real embutida: `false`
- writer chamado: `false`
- secrets publicados: `false`

## C12.3.3

- c12_3_3_blocked: `true`
- cause: `lab_firstboot_autoconfig_not_effective`
- c12_1_4_reusable_for_boot_validation: `false`

## Inspecao C12.1.4

- c12_1_4_image_inspected: `true`
- autoconfig_present_in_image: `true`
- gate_expected_path_matches: `true`
- rootfs_lab_bootstrap_proven: `false`
- ready_for_card_write_by_rootfs: `false`

Classificacao:

```text
firstboot_conf_present_but_not_autonomously_applied
```

## Correcao Aplicada

- rootfs_validation_added: `true`
- build_fix_required: `true`
- lab_bootstrap_service_added: `true`
- lab_bootstrap_ordered_before_gate: `true`
- validation_requires_rootfs_inspection: `true`

## C12.1.6

- build_success: `true`
- image_path:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-6_minimal.img`
- sha256:
  `b64808a7ce23d7c19422c816ca558605d39b495019ecac0bb480345bff711a67`
- overlayroot_included: `true`
- initramfs_generated_after_overlayroot: `true`
- rootfs_firstboot_autoconfig_proven: `true`
- rootfs_lab_bootstrap_proven: `true`
- ready_for_card_write_by_rootfs: `true`
- ready_for_c12_2_3_card_write: `true`

## Proibicoes Mantidas

Nao foram publicados:

- conteudo do `firstboot.conf`;
- senha;
- SSID;
- chave privada;
- API key;
- IP/MAC/DNS;
- config real.
