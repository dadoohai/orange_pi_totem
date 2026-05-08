# C12.1.11 - Build Image-lab Overlayfs Built-in

Data: 2026-05-08

## Objetivo

Gerar uma nova image-lab com `overlayroot` oficial e `overlayfs` built-in no
kernel:

```text
CONFIG_OVERLAY_FS=y
```

Esta imagem continua sendo image-lab, nao imagem final de producao. C12.4 segue
bloqueado ate boot real validar a semantica read-only.

## Politica de Firstboot

Para esta rodada foi escolhido o modo:

```text
lab_firstboot_mode=private_disposable_lab
```

Motivo: a proxima validacao de placa precisa de caminho SSH automatico para
diagnostico. O arquivo privado foi validado fora do Git e usado apenas como
artefato descartavel de laboratorio.

Garantias:

- `artifact_private=true`;
- `final_image=false`;
- `firstboot_conf_committed=false`;
- `firstboot_conf_contents_published=false`;
- conteudo do arquivo privado nao foi publicado;
- imagem final nunca deve usar esse modo.

O modo sintetico sem segredo permanece permitido para imagens que podem ser
gravadas, mas ele nao e adequado para validacao automatica por SSH sem
first-login manual.

## Pre-flight

O pre-flight passou:

- branch/base mantidos como `orangepizero3` / `bookworm` / `current`;
- `BUILD_MINIMAL=yes`;
- `BUILD_DESKTOP=no`;
- `NETWORKING_STACK=network-manager`;
- `BSPFREEZE=yes`;
- userpatch de kernel e config completa, nao fragmento parcial;
- `CONFIG_OVERLAY_FS=y` presente exatamente uma vez;
- `CONFIG_OVERLAY_FS=m` ausente;
- `overlayroot=tmpfs` mantido;
- politica journald volatil mantida;
- layout `/data` mantido;
- criterio antigo `root_write_blocked=true` nao e mais blocker para overlayroot;
- hooks antigos de fallback modular/diagnostico nao devem estar presentes na
  imagem validada.

## Resultado do Build

O build foi iniciado com:

```text
C12_IMAGE_TAG=c12-1-11
C12_IMAGE_VERSION=c12.1.11
C12_KERNEL_OVERLAYFS_BUILTIN=1
C12_REQUIRE_LAB_FIRSTBOOT_CONF=1
C12_LAB_FIRSTBOOT_CONF_KIND=private
```

O kernel compilou e foi empacotado com sucesso:

```text
kernel_version=6.12.58-sunxi64
kernel_built=true
kernel_packaged=true
```

A falha ocorreu depois, na fase de rootfs/image, durante `apt-get update`
dentro da imagem:

```text
build_success=false
image_built=false
failure_category=BUILD_HOST_CHROOT_APT_MEMORY_ERROR
```

Categoria sanitizada do erro:

```text
apt_update_inside_image_failed=true
apt_error_category=cannot_allocate_memory_while_reading_backports_inrelease
```

Nao houve imagem C12.1.11, checksum, package manifest final ou integration
manifest final.

## Interpretacao

O resultado nao invalida a decisao tecnica da ADR-0012. A falha observada nao
foi no `CONFIG_OVERLAY_FS=y`, nem no `overlayroot`, nem nos scripts Dadooh. Foi
um erro do ambiente de build durante atualizacao de listas APT dentro do chroot
da imagem, depois do kernel ja ter sido compilado.

## Artefatos

Gerados:

- build wrapper log;
- log Armbian completo;
- kernel packages no cache/output do Armbian Build.

Nao gerados:

- image file C12.1.11;
- SHA256 da imagem;
- package manifest final da imagem;
- read-only integration manifest final da imagem.

## Status

- `image_version=c12.1.11`;
- `build_success=false`;
- `kernel_overlayfs_builtin_preflight=true`;
- `kernel_built=true`;
- `kernel_packaged=true`;
- `image_built=false`;
- `card_written=false`;
- `boards_touched=false`;
- `ssh_used=false`;
- `writer_called=false`;
- `secrets_published=false`;
- `ready_for_c12_2_7_card_write=false`;
- `c12_4_blocked=true`.

## Proximo Passo

Resolver o blocker do ambiente de build antes de repetir C12.1.11. A repeticao
deve reutilizar os pacotes de kernel ja compilados quando o Armbian Build
permitir, e so liberar C12.2.7 depois de gerar imagem, checksum e validacao
offline.
