# C12.3.9 - Initramfs Overlay Module Diagnostics

Data: 2026-05-08

## Objetivo

Diagnosticar por que `overlay.ko`, embora apontado como presente no
`initrd`/`uInitrd` por inspecoes offline, nao fica carregado/registrado no
runtime do initramfs quando o `overlayroot` roda.

Nao houve uso da dev, da placa teste antiga, writer, config real, Wi-Fi,
NetworkManager, instalacao de pacotes, poweroff ou corte seco.

## Metodo

Foi instalado um hook temporario `init-top` apenas para diagnostico. O hook
registrou somente categorias e booleans em `/run/initramfs`, sem dmesg bruto e
sem publicar paths privados ou secrets.

O hook foi instalado com backup, `update-initramfs` retornou 0, `uInitrd`
continuou nao vazio, houve reboot controlado, SSH voltou e o rollback foi
executado depois da coleta.

## Resultado

O diagnostico confirmou:

- `/proc` estava disponivel no initramfs;
- `overlay` nao estava em `/proc/filesystems` antes do teste;
- `modprobe` estava presente;
- `insmod` estava presente;
- `modules.dep` estava presente;
- `modprobe overlay` retornou zero;
- `overlay` continuou ausente de `/proc/filesystems` depois do `modprobe`;
- `overlay.ko` nao foi encontrado no caminho de modulo esperado pelo hook;
- `insmod` nao foi tentado porque o arquivo do modulo nao foi resolvido;
- `vermagic` ficou `unknown`, porque o arquivo do modulo nao foi encontrado.

O root permaneceu:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- `systemctl_failed_count=0`;
- `public_state=config_missing`.

## Classificacao

```text
OVERLAY_MODULE_PATH_INVALID
```

C12.3.8 provou que o initramfs efetivo possui artefatos relacionados ao
`overlay`; C12.3.9 refinou que, no runtime do initramfs, o arquivo do modulo
nao esta resolvivel no caminho esperado quando o hook roda. Isso explica por que
`modprobe overlay` pode retornar zero sem tornar `overlay` visivel em
`/proc/filesystems`.

## Decisao

Esta causa parece corrigivel no build da imagem, sem trocar imediatamente de
mecanismo read-only:

```text
C12.1.9_REBUILD_WITH_INITRAMFS_MODULE_PATH_FIX
```

C12.1.9 deve garantir que o layout/caminho dos modulos no initramfs efetivo
exponha `overlay.ko` no local esperado antes do `overlayroot` rodar. C12.4
continua bloqueado ate uma imagem bootar com `read_only_enabled=true`,
`overlay_active=true` e `root_write_blocked=true`.

## Atualizacao C12.1.9

C12.1.9 reconstruiu a imagem-lab com validacao do caminho efetivo resolvido por
symlink no initramfs usr-merged:

```text
/lib -> usr/lib
```

A imagem agora inclui hook `init-top` para carregar `overlay` e fallback por
`insmod` usando `/lib/modules/<kernel>/kernel/fs/overlayfs`. A validacao offline
provou:

- `overlay_module_effective_path_present=true`;
- `modules_dep_effective_path_present=true`;
- `modules_dep_references_overlay=true`;
- `effective_boot_initramfs_overlay_resolvable=true`;
- `effective_boot_initramfs_valid=true`.

C12.2.5 pode gravar a imagem C12.1.9. C12.4 segue bloqueado ate a validacao em
placa provar read-only real.

## Status

- `diagnostic_hook_installed=true`
- `reboot_executed=true`
- `ssh_returned=true`
- `rollback_executed=true`
- `diagnostic_hook_present_after=false`
- `ready_for_c12_1_9_rebuild=true`
- `c12_4_blocked=true`
