# C12.3.8 - Read-only Mechanism Decision

Data: 2026-05-08

## Objetivo

Confirmar onde o mecanismo `overlayroot` falha dentro do initramfs da
image-lab C12.1.8 e decidir o proximo passo sem repetir enable, sem alterar a
placa e sem iniciar C12.4.

Nao houve reboot, remount, writer, config real, Wi-Fi, NetworkManager,
instalacao de pacotes, poweroff ou corte seco.

## O Que Foi Inspecionado

Na placa `lab_board`, a inspecao confirmou:

- kernel `6.12.58-current-sunxi64`;
- `overlayroot=tmpfs` chega ao cmdline;
- `/etc/overlayroot.conf` esta em `overlayroot=tmpfs`;
- boot script usa `uInitrd`;
- `uInitrd` existe, e o payload corresponde ao `initrd.img`;
- initramfs efetivo contem `scripts/init-bottom/overlayroot`;
- initramfs efetivo contem `overlay.ko`;
- initramfs efetivo contem `modules.dep` e `modules.alias`;
- initramfs efetivo contem `modprobe`;
- hook C12.3.7 `dadooh-force-overlay` esta no initramfs.

Tambem foi lido o comportamento do script `overlayroot` instalado pelo pacote:

- ele chama `modprobe`/driver antes de montar;
- ele checa `/proc/filesystems`;
- ele usa `mount -t overlay`;
- ele roda em fase `init-bottom`;
- ele pode sair sem montar se o driver nao aparecer como filesystem.

## Resultado

O root continua gravavel:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- root continua `ext4 rw`.

A falha ficou mais precisa que C12.3.6/C12.3.7:

```text
OVERLAY_MODULE_PRESENT_BUT_NOT_REGISTERED_IN_INITRAMFS_RUNTIME
```

Ou seja: o problema nao e mais ausencia simples de `overlay.ko`, `modules.dep`
ou `modprobe` no initramfs. O modulo esta presente e a tentativa de carga
acontece, mas `overlay` nao aparece em `/proc/filesystems` no runtime do
initramfs; por isso o `overlayroot` nao chega a montar o overlay.

## Decisao

O caminho `overlayroot` ainda nao esta descartado, mas nao esta pronto para novo
build simples. A proxima rodada deve investigar carregamento/registro do driver
no initramfs ou compatibilidade kernel/initramfs:

```text
C12.3.9_FIX_INITRAMFS_MODULE_LOADING_OR_KERNEL_OVERLAY_COMPATIBILITY
```

Nao iniciar C12.1.9 como rebuild apenas com modulo/hook, e nao iniciar C12.4.

## Status

- `read_only_validated=false`
- `c12_4_blocked=true`
- `ready_for_c12_1_9_rebuild=false`
- `next_step=C12.3.9_FIX_INITRAMFS_MODULE_LOADING_OR_KERNEL_OVERLAY_COMPATIBILITY`

## Atualizacao C12.3.9

C12.3.9 instalou um hook temporario de diagnostico no initramfs, com backup,
reboot controlado e rollback. O hook mostrou que `/proc` estava disponivel,
`modprobe` e `insmod` estavam presentes, `modules.dep` existia e
`modprobe overlay` retornou zero. Mesmo assim, `overlay` continuou ausente em
`/proc/filesystems`.

A causa foi refinada para:

```text
OVERLAY_MODULE_PATH_INVALID
```

No runtime do initramfs, o arquivo `overlay.ko` nao foi encontrado no caminho de
modulo esperado pelo hook. C12.1.9 pode comecar como rebuild focado em corrigir
o layout/caminho de modulos no initramfs efetivo. C12.4 continua bloqueado.

## Atualizacao C12.1.9

C12.1.9 gerou nova imagem-lab com:

- `overlayroot=tmpfs` nos boot args;
- hook `init-top` para `modprobe overlay`;
- fallback `insmod` por `/lib/modules/<kernel>/kernel/fs/overlayfs`;
- validacao offline do caminho efetivo resolvido por `/lib -> usr/lib`;
- `effective_boot_initramfs_overlay_resolvable=true`.

Isso libera a gravacao C12.2.5, mas nao libera C12.4. A decisao de read-only
so muda depois de boot em placa provar `overlay_active=true` e
`root_write_blocked=true`.
