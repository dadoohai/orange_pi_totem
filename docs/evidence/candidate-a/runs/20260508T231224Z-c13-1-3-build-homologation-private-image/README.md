# C13.1.3 - Build Homologation Private Image

Data: 2026-05-08

## Resultado

```text
image_built=true
image_path=/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c13-1-3-homolog-private_minimal.img
image_sha256=3a76d51880d944fe5430782ad2cf84866573c219cdf6a719c004e38c5c2fe6eb
artifact_private=true
final_image=false
not_for_production=true
not_for_distribution=true
homologation_private_values_embedded=true
seed_source_outside_repo=true
seed_permissions_ok=true
seed_content_published=false
seed_embedded_path=/data/state/totem-settings/private-values.seed.json
tmp_private_values_dependency=false
offline_validation_passed=true
ready_for_multi_card_homologation=true
card_written=false
boards_touched=false
ssh_used=false
writer_called=false
poweroff_executed=false
power_cut_tested=false
apt_upgrade_executed=false
secrets_published=false
c12_readonly_blocked=true
c12_4_blocked=true
```

## Build

O build usou a seed privada de homologacao a partir de arquivo fora do repo,
validado apenas por categorias/permissoes. O conteudo nao foi impresso nem
copiado para evidencia.

O artefato e privado e descartavel para homologacao. Ele nao e imagem final,
nao e producao e nao deve ser distribuido.

## Validacao Offline

```text
homologation_seed_present_in_rootfs=true
homologation_seed_mode_0600=true
homologation_seed_parent_private=true
homologation_seed_marker_present=true
homologation_seed_required_categories_present=true
homologation_seed_content_published=false
firstboot_conf_committed=false
firstboot_conf_contents_published=false
lab_firstboot_mode=private_disposable_lab
kernel_config_overlayfs_builtin=true
overlayroot_included=true
uinitrd_nonempty=true
effective_boot_initramfs_valid=true
modular_overlay_fallback_hooks_present=false
diagnostic_initramfs_hooks_present=false
```

## Observacoes

O build precisou contornar uma falha de memoria no `apt-get update` em chroot
arm64 emulado removendo `bookworm-backports` das fontes APT da imagem-lab antes
dos updates finais. A imagem de homologacao nao depende de backports.

C12 read-only permanece bloqueado; C12.4 continua bloqueado.
