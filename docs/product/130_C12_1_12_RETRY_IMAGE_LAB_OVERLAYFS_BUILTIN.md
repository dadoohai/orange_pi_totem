# C12.1.12 - Retry Image-lab Overlayfs Built-in

Data: 2026-05-08

## Objetivo

Repetir o build da image-lab apos o blocker C12.1.11, preservando caches e
reaproveitando os pacotes de kernel ja compilados com:

```text
CONFIG_OVERLAY_FS=y
```

Nao houve uso de placas, SSH, gravacao de cartao, writer, Wi-Fi real,
provisionamento de config real, poweroff ou corte seco.

## Diagnostico do Blocker Anterior

C12.1.11 falhou depois do kernel compilar e empacotar. A falha ocorreu na fase
rootfs/image, durante `apt-get update` dentro do chroot:

```text
BUILD_HOST_CHROOT_APT_MEMORY_ERROR
cannot_allocate_memory_while_reading_backports_inrelease
```

Antes do retry, o host estava saudavel:

- memoria disponivel: aproximadamente `8.7GiB`;
- swap disponivel: aproximadamente `2.9GiB`;
- WSL2 detectado;
- nenhum container ativo consumindo memoria;
- espaco em disco suficiente no workspace/cache.

Classificacao:

```text
probable_cause=rootfs_apt_memory_pressure_transient
```

## Kernel Reaproveitado

Os pacotes locais do kernel foram preservados e reaproveitados:

```text
kernel_deb_reusable=true
kernel_reused=true
kernel_rebuild_executed=false
```

O `linux-image` foi extraido em diretorio temporario e o arquivo
`/boot/config-*` confirmou:

```text
CONFIG_OVERLAY_FS=y
CONFIG_OVERLAY_FS=m absent
```

Hashes registrados:

- linux-image:
  `098b9ad49ebb74ad88d2fe2249bbbd11d8c79845fbae5124c68fa7699f6988ad`;
- linux-dtb:
  `062d5d6a94a0fde5deb75b9da574d9fe25eeb657e9a0b9118e168c06015a5060`;
- linux-headers:
  `83d543f071183ac5026b9a999c0bc2258d15a632d4f1a1018f65d3a526bdfcf5`;
- linux-u-boot:
  `88d0cdf065b337fee50121f36dc354fa311349d6b32b1feccc7d5e9811102a3e`.

## Build C12.1.12

O build foi executado com:

```text
C12_IMAGE_TAG=c12-1-12
C12_IMAGE_VERSION=c12.1.12
C12_KERNEL_OVERLAYFS_BUILTIN=1
C12_REQUIRE_LAB_FIRSTBOOT_CONF=1
C12_LAB_FIRSTBOOT_CONF_KIND=private
```

O conteudo do `firstboot.conf` privado nao foi impresso, documentado ou
commitado.

Resultado:

```text
build_success=true
image_built=true
kernel_reused=true
kernel_rebuild_executed=false
```

Imagem:

```text
/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-12_minimal.img
```

SHA256:

```text
1220aab2272b5e6fa3430b6aab1c180624441104ab6b4ab7a1a1932fc8373a81
```

## Validacao Offline

A validacao offline passou:

```text
c12_1_image_lab_artifacts=ok
```

Campos principais:

- `kernel_config_overlayfs_builtin=true`;
- `rootfs_kernel_config_overlayfs_builtin=true`;
- `overlayroot_included=true`;
- `overlayroot_tmpfs_configured=true`;
- `overlay_module_required=false`;
- `overlayfs_builtin_expected=true`;
- `initrd_contains_overlayroot_hook=true`;
- `uinitrd_exists=true`;
- `uinitrd_nonempty=true`;
- `uinitrd_payload_matches_initrd_img=true`;
- `effective_boot_initramfs_valid=true`;
- `modular_overlay_fallback_hooks_present=false`;
- `diagnostic_initramfs_hooks_present=false`;
- `journald_volatile` sera validado no boot real;
- `/data` layout foi incluido pela integracao C12.

Como esperado para `CONFIG_OVERLAY_FS=y`, a validacao nao exige `overlay.ko` no
initramfs:

```text
overlay_module_required=false
```

## Firstboot Lab

Modo usado:

```text
lab_firstboot_mode=private_disposable_lab
artifact_private=true
final_image=false
firstboot_conf_committed=false
firstboot_conf_contents_published=false
ready_for_c12_3_boot_ssh_validation=true
require_manual_firstboot=false
```

Esse modo e permitido somente para image-lab descartavel. A imagem final nunca
deve embutir esse arquivo privado.

## Status

- `image_version=c12.1.12`;
- `image_built=true`;
- `card_written=false`;
- `boards_touched=false`;
- `ssh_used=false`;
- `writer_called=false`;
- `secrets_published=false`;
- `ready_for_c12_2_7_card_write=true`;
- `ready_for_c12_3_boot_ssh_validation=true`;
- `c12_4_blocked=true`.

## Proximo Passo

C12.2.7 pode gravar o cartao de teste com a C12.1.12. C12.3.17 deve validar em
boot real a semantica correta:

- `overlay_active=true`;
- root mount type `overlay` ou equivalente;
- escrita fora de `/data` nao persiste apos reboot;
- escrita em `/data` persiste apos reboot;
- `/data`, `/tmp` e `/run` gravaveis;
- journald volatil;
- Dadooh acessivel para diagnostico.

C12.4 continua bloqueado ate essa validacao passar.
