# C12.1.8 - Rebuild Image-Lab com uInitrd Valido

Data: 2026-05-07

## Objetivo

Reconstruir a imagem-lab C12 com `uInitrd` efetivo valido para o boot do
Orange Pi Zero 3. A rodada corrige o bloqueio C12.1.7 classificado como:

```text
UINITRD_NOT_UPDATED
```

Nenhuma placa foi tocada, nenhum cartao foi gravado, nenhum writer foi chamado
e nenhum secret foi publicado.

## Causa

C12.1.7 mostrou que a imagem C12.1.6 tinha `overlayroot="tmpfs"` e
`initrd.img` com hook `overlayroot`, mas o boot script usa `uInitrd`.

A validacao antiga aceitava o manifesto do initramfs sem provar o initramfs
efetivo carregado pelo boot. C12.1.8 passou a validar o payload real de
`uInitrd`, seguindo o symlink para `uInitrd-<kernel>`, extraindo o ramdisk
U-Boot e comparando com `initrd.img`.

## Correcao

O build agora:

- instala `overlayroot`;
- aplica `/etc/overlayroot.conf` com `overlayroot="tmpfs"`;
- instala um hook/marker seguro em `/etc/initramfs-tools/hooks`;
- força o initramfs final a incorporar esse marker;
- gera/converte `uInitrd` pelo fluxo Armbian `post-update.d/99-uboot`;
- falha a validacao se `uInitrd` estiver ausente, vazio ou divergente de
  `initrd.img`.

O marker nao contem segredo:

```text
c12_overlayroot_initramfs_marker=present
overlayroot_config_expected=tmpfs
```

## Artefato

Imagem C12.1.8:

```text
/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-8_minimal.img
```

SHA256:

```text
7fbc9a0abc39d39b5fc0803d5f935baaf1795bddc6707e18dbf1d7c804ad830d
```

Build log:

```text
/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-2a197de8-ef86-4e09-8ec0-61bc0fa180b0.log
```

## Validacao Offline

Validado nos artefatos:

- `overlayroot_included=true`;
- `initrd_img_exists=true`;
- `initrd_contains_overlayroot_hook=true`;
- `initrd_contains_overlay_module=true`;
- `initrd_contains_c12_overlayroot_marker=true`;
- `uinitrd_exists=true`;
- `uinitrd_nonempty=true`;
- `uinitrd_payload_matches_initrd_img=true`;
- `uinitrd_contains_overlayroot_hook=true`;
- `uinitrd_contains_overlay_module=true`;
- `uinitrd_contains_c12_overlayroot_marker=true`;
- `uinitrd_generated_after_overlayroot=true`;
- `uinitrd_generated_after_initrd_img=true`;
- `boot_script_uses_uinitrd=true`;
- `effective_boot_initramfs_valid=true`;
- `rootfs_firstboot_autoconfig_proven=true`;
- `no secrets`.

## Guardrails

- placas tocadas: `false`;
- cartao gravado: `false`;
- config real embutida: `false`;
- writer chamado: `false`;
- Wi-Fi/NetworkManager de placa alterado: `false`;
- imagem final de producao: `false`.

## Proximo Passo

C12.2.4 deve gravar a imagem C12.1.8 em cartao de teste novo/descartavel.
Depois, C12.3.x deve validar boot, SSH, firstboot lab, `config_missing` visual
e principalmente:

- `read_only_enabled=true`;
- `overlay_active=true`;
- `root_write_blocked=true`;
- `/data`, `/tmp` e `/run` gravaveis.

C12.4 continua bloqueado ate essa validacao em placa passar.
