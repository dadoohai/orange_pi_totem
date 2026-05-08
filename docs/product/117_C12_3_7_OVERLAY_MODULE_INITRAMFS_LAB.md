# C12.3.7 - Overlay Module Initramfs Lab

Data: 2026-05-08

## Objetivo

Testar na placa image-lab descartavel se forcar o modulo `overlay` dentro do
initramfs resolveria a ativacao do `overlayroot`.

Nao houve uso da dev, da placa teste antiga, writer, config real, Wi-Fi,
NetworkManager, instalacao de pacotes, poweroff ou corte seco.

## Estado Inicial

A placa C12.1.8 ja estava com:

- `overlayroot=tmpfs` no cmdline;
- `overlayroot` rodando no initramfs;
- `initrd` e `uInitrd` contendo `overlay.ko`;
- root ainda `ext4 rw`;
- erro classificado como `overlay_driver_unavailable_in_initramfs`.

## Hipoteses Testadas

Foram usados os dois ciclos permitidos:

- `H1_FORCE_MODULE`: adicionar `overlay` a
  `/etc/initramfs-tools/modules`, regenerar initramfs/uInitrd e rebootar;
- `H2_FORCE_LOAD_HOOK`: adicionar hook minimo `init-top` para executar
  `modprobe overlay` antes do `overlayroot`, regenerar initramfs/uInitrd e
  rebootar.

Ambas as hipoteses tiveram backup e rollback em
`/data/state/totem-overlayroot-lab`.

## Resultado

H1 entrou no initramfs/uInitrd, mas nao ativou o overlay. H2 tambem entrou no
initramfs/uInitrd, mas o resultado permaneceu:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- root continua `ext4 rw`;
- `/data`, `/tmp` e `/run` continuam gravaveis;
- SSH voltou apos os reboots;
- `systemctl_failed_count=0`.

## Classificacao

O mecanismo segue bloqueado:

```text
OVERLAY_DRIVER_UNAVAILABLE_IN_INITRAMFS_RUNTIME
```

Forcar a inclusao do modulo e executar `modprobe overlay` antes do
`overlayroot` nao foi suficiente para fazer `overlay` aparecer como filesystem
disponivel no momento em que o `overlayroot` monta o root.

## Decisao

C12.1.9 nao deve ser apenas um rebuild com preload simples de modulo. O proximo
passo precisa ser uma decisao tecnica nova sobre o mecanismo:

- investigar compatibilidade do `overlayroot` com o initramfs/kernel desta base;
- avaliar patch no hook do pacote ou ordem real de execucao no initramfs;
- ou substituir o mecanismo read-only antes de nova imagem.

C12.4 permanece bloqueado.

## Atualizacao C12.3.8

C12.3.8 fez apenas diagnostico read-only, sem alterar a placa. A causa foi
refinada: o initramfs efetivo contem `overlay.ko`, `modules.dep`, `modules.alias`,
`modprobe`, o hook `overlayroot` e o hook C12.3.7. Mesmo assim, quando o
`overlayroot` roda, `overlay` nao aparece em `/proc/filesystems` e o mount de
overlay nao e tentado.

Classificacao:

```text
OVERLAY_MODULE_PRESENT_BUT_NOT_REGISTERED_IN_INITRAMFS_RUNTIME
```

Proximo passo recomendado:

```text
C12.3.9_FIX_INITRAMFS_MODULE_LOADING_OR_KERNEL_OVERLAY_COMPATIBILITY
```

C12.1.9 nao deve ser rebuild simples com modulo/hook. C12.4 permanece
bloqueado.

## Atualizacao C12.3.9

O diagnostico com hook temporario no initramfs refinou a causa para:

```text
OVERLAY_MODULE_PATH_INVALID
```

O hook confirmou `/proc` disponivel, `modprobe`/`insmod` presentes e
`modprobe overlay` retornando zero, mas `overlay.ko` nao foi encontrado no
caminho de modulo esperado no runtime do initramfs e `overlay` nao apareceu em
`/proc/filesystems`. O hook foi removido por rollback.

Com isso, C12.1.9 pode ser planejado como rebuild focado em corrigir layout ou
caminho de modulos no initramfs efetivo. C12.4 permanece bloqueado.
