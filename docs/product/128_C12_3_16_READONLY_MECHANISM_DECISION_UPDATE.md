# C12.3.16 - Read-only Mechanism Decision Update

Data: 2026-05-08

## Objetivo

Atualizar formalmente a decisao tecnica apos C12.3.15 e corrigir os criterios
de validacao para o proximo experimento de read-only.

Nao houve uso de placas, gravacao de cartao, nova imagem, writer, config real,
Wi-Fi/NetworkManager, poweroff ou corte seco.

## Decisao Atualizada

A linha abaixo esta encerrada:

```text
overlayroot + overlay.ko carregado como modulo no initramfs
```

Ela foi investigada ate o limite util entre C12.3.6 e C12.3.15. O resultado
final foi:

```text
INITRAMFS_MODULE_LOADING_UNSUPPORTED
```

A nova decisao, registrada na ADR-0012, e manter `overlayroot`, mas fazer o
proximo experimento com `overlayfs` built-in no kernel:

```text
CONFIG_OVERLAY_FS=y
```

Isso remove a dependencia de `modprobe`, `insmod` e `modules.dep` no runtime do
initramfs, que foi exatamente o ponto de falha observado.

## Criterios de Validacao Corrigidos

O criterio antigo `root_write_blocked=true` nao e suficiente nem sempre correto
para `overlayroot`. Com overlayroot, o root aparente pode aceitar escrita,
porque o merged root e um overlay volatil.

O criterio correto passa a ser semantico:

- `overlay_active=true`;
- `root_mount_type=overlay` ou equivalente;
- `overlay` aparece em `/proc/filesystems`;
- o lower/root fisico esta protegido/read-only quando detectavel;
- um arquivo criado fora de `/data` nao persiste apos reboot;
- um arquivo criado em `/data` persiste apos reboot;
- `/data`, `/tmp` e `/run` seguem gravaveis;
- `journald_volatile=true`;
- `readonly_semantics_valid=true`.

Novos campos esperados para validacao em placa:

- `root_apparent_write_allowed`;
- `root_test_file_created`;
- `root_test_file_persisted_after_reboot`;
- `data_test_file_persisted_after_reboot`;
- `readonly_semantics_valid`.

## Build C12.1.11

O runner de build foi preparado para o proximo experimento com:

```text
C12_IMAGE_TAG=c12-1-11
C12_IMAGE_VERSION=c12.1.11
C12_REQUIRE_LAB_FIRSTBOOT_CONF=1
C12_LAB_FIRSTBOOT_CONF=/path/privado/firstboot.conf
C12_KERNEL_OVERLAYFS_BUILTIN=1
```

O build deve copiar a configuracao completa do kernel:

```text
/home/builder/totem-os/armbian-build-v25.11/config/kernel/linux-sunxi64-current.config
```

para o userpatch Armbian:

```text
userpatches/linux-sunxi64-current.config
```

e alterar somente o necessario para garantir:

```text
CONFIG_OVERLAY_FS=y
```

Nao foi criado fragmento parcial de Kconfig.

## Status

- `overlayroot_module_initramfs_path_status=blocked`;
- `next_experiment=kernel_overlayfs_builtin`;
- `required_kernel_config=CONFIG_OVERLAY_FS=y`;
- `read_only_validated=false`;
- `c12_4_blocked=true`;
- `ready_for_c12_1_11_build=true`.

## Proximo Passo

C12.1.11 pode comecar como build de nova image-lab com kernel overlayfs
built-in. C12.4 segue bloqueado ate boot real validar a semantica read-only.

## Atualizacao C12.1.11

C12.1.11 iniciou o build com `CONFIG_OVERLAY_FS=y` e pre-flight aprovado. O
kernel foi compilado e empacotado, mas a imagem nao foi gerada porque o Armbian
Build falhou na fase de rootfs/image durante `apt-get update` dentro do chroot,
com categoria sanitizada:

```text
BUILD_HOST_CHROOT_APT_MEMORY_ERROR
```

Essa falha nao altera a decisao tecnica da ADR-0012. O proximo passo continua
sendo gerar uma image-lab com overlayfs built-in, mas o ambiente de build deve
passar dessa etapa e produzir imagem, checksum e validacao offline antes de
C12.2.7.
